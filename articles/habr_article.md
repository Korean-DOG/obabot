# Ваш aiogram-бот теперь работает в Max. Да, вот так просто

Если у тебя есть бот на aiogram — ты уже написал бота для Max. Просто ещё не знаешь об этом.

Покажу как за 5 минут (из которых 4 — это `pip install`) запустить своего Telegram-бота в мессенджере Max. Без переписывания, без изучения нового API, без боли.

## Сначала покажу, потом объясню

Вот типичный бот на aiogram 3.x. Ничего необычного:

```python
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command

bot = Bot(token="TELEGRAM_TOKEN")
dp = Dispatcher()
router = Router()
dp.include_router(router)

@router.message(Command("start"))
async def start(message):
    await message.answer("Привет!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
```

А теперь — тот же бот, но через obabot:

```python
from obabot import create_bot
from obabot.filters import Command

bot, dp, router = create_bot(tg_token="TELEGRAM_TOKEN")

@router.message(Command("start"))
async def start(message):
    await message.answer("Привет!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
```

Что изменилось? Две строки импорта и одна строка инициализации. Хендлеры — один в один. Фильтры — те же. Всё остальное — без изменений.

Окей, а теперь фокус. Добавляем Max:

```python
bot, dp, router = create_bot(
    tg_token="TELEGRAM_TOKEN",
    max_token="MAX_TOKEN"
)
```

Всё. Бот работает на двух платформах. Один `start_polling` поднимает polling на обеих. Один хендлер обрабатывает сообщения отовсюду.

Хочешь знать, откуда пришло сообщение?

```python
@router.message(Command("start"))
async def start(message):
    await message.answer(f"Привет с {message.platform}!")
```

Telegram-пользователь увидит «Привет с telegram!», Max-пользователь — «Привет с max!».

> Здесь можно вставить два скриншота рядом: диалог в Telegram и диалог в Max с одним и тем же ботом.

## Зачем это вообще нужно

Давай честно. Если у тебя бот только для себя и трёх друзей — тебе это не нужно. Закрывай статью, иди пить чай.

Но если ты делаешь бота для бизнеса, для команды, для продукта — вот тебе реальность:

**Аудитория фрагментирована.** Часть пользователей сидит в Telegram, часть — в Max. И бизнес говорит: «Нам нужно быть везде». А ты такой сидишь и понимаешь, что это значит:

- Изучить API Max (он другой)
- Освоить `umaxbot` (это не aiogram, там свои концепции)
- Переписать хендлеры, клавиатуры, FSM-логику
- Написать тесты заново
- Поддерживать два кодбейза параллельно

Это не "ещё один токен добавить". Это реально недели работы. И потом — двойной багфикс, двойное тестирование, двойная поддержка. На каждый чих.

**obabot решает это одной строкой.** Не новый фреймворк. Не "очередная абстракция поверх абстракции". Это прозрачный адаптер: для Telegram работает нативный aiogram (без оверхеда вообще), а для Max — лёгкая обёртка, которая превращает umaxbot-объекты в aiogram-подобные.

Ты не переучиваешься. Ты не мигрируешь. Ты просто добавляешь `max_token` и идёшь заниматься делами.

## Для кого это

- **У тебя уже есть бот на aiogram** и нужно запустить его в Max → меняешь импорты, добавляешь токен, готово.
- **Ты знаешь aiogram**, но не знаешь umaxbot → и не нужно знать, obabot сам разберётся.
- **Стартап или продуктовая команда** — один кодбейс, два мессенджера, вдвое меньше работы.
- **Только Max, без Telegram?** Тоже работает. Просто передай только `max_token`.

## Как это работает под капотом (коротко)

Не буду грузить архитектурными диаграммами, но если интересно — вот суть:

**Прокси-объекты.** `create_bot()` возвращает `ProxyBot`, `ProxyDispatcher`, `ProxyRouter`. Они выглядят и ведут себя как родные aiogram-объекты, но умеют маршрутизировать вызовы на нужную платформу.

**Адаптеры для Max.** Когда приходит сообщение из Max, оно оборачивается в `MaxMessageAdapter` — объект с теми же атрибутами и методами, что и у `aiogram.types.Message`. У него есть `text`, `from_user`, `chat`, `answer()`, `reply()`, `delete()`, `edit_text()`. Твой хендлер не видит разницы.

**Telegram без накладных расходов.** Для Telegram используется нативный aiogram без каких-либо обёрток. Единственное, что добавляется — атрибут `message.platform = "telegram"`. Всё. Производительность — ровно такая же, как у чистого aiogram.

**Что реально работает из коробки:**

- Хендлеры (`@router.message`, `@router.callback_query`, `@router.edited_message` и т.д.)
- Все фильтры aiogram (`Command`, `F`, `StateFilter`)
- FSM — состояния, группы состояний, контекст
- Инлайн-клавиатуры и callback-запросы
- Общее FSM-хранилище для обеих платформ (хоть MemoryStorage, хоть Redis)
- Тестовый режим без реальных токенов

## Пошаговая миграция (реально 5 минут)

### Шаг 1. Установка

```bash
pip install obabot
```

Зависимости `aiogram` и `umaxbot` подтянутся автоматически.

### Шаг 2. Меняем импорты

Было:
```python
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
```

Стало:
```python
from obabot import create_bot
from obabot.filters import Command, F
from obabot.fsm import State, StatesGroup, FSMContext
from obabot.types import InlineKeyboardMarkup, InlineKeyboardButton
```

### Шаг 3. Меняем инициализацию

Было:
```python
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)
```

Стало:
```python
bot, dp, router = create_bot(tg_token=TOKEN)
```

Четыре строки → одна. `include_router` больше не нужен — `create_bot` делает это сам.

### Шаг 4. Добавляем Max (опционально)

```python
bot, dp, router = create_bot(
    tg_token=TG_TOKEN,
    max_token=MAX_TOKEN
)
```

### Шаг 5. Запускаем

```python
await dp.start_polling(bot)
```

Одна строка — polling на всех платформах.

**Всё.** Хендлеры, фильтры, FSM, клавиатуры — трогать не нужно. Они работают как работали.

## FSM — тоже из коробки

Вот полный пример с состояниями, который работает на обеих платформах:

```python
from obabot import create_bot
from obabot.filters import Command, F
from obabot.fsm import State, StatesGroup, FSMContext, MemoryStorage

bot, dp, router = create_bot(
    tg_token=TG_TOKEN,
    max_token=MAX_TOKEN,
    fsm_storage=MemoryStorage()
)

class Form(StatesGroup):
    waiting_name = State()
    waiting_age = State()

@router.message(Command("start"))
async def cmd_start(message, state: FSMContext):
    await state.set_state(Form.waiting_name)
    await message.answer("Как тебя зовут?")

@router.message(Form.waiting_name)
async def process_name(message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.waiting_age)
    await message.answer(f"Привет, {message.text}! Сколько тебе лет?")

@router.message(Form.waiting_age)
async def process_age(message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await message.answer(
        f"Готово! {data['name']}, {message.text} лет. "
        f"Платформа: {message.platform}"
    )
```

Хочешь Redis вместо MemoryStorage? Подставляй `RedisStorage` — он тоже работает. Одно хранилище состояний для обеих платформ.

## Тестовый режим

Для юнит-тестов не нужны реальные токены:

```python
bot, dp, router = create_bot(test_mode=True)
```

Или через переменную окружения `TESTING=1`. В этом режиме не открываются соединения, не нужны токены — можно спокойно тестировать логику хендлеров.

## Что дальше

obabot — проект живой и развивающийся. Сейчас версия 0.2.0, покрытие интерфейса aiogram — около 90-95% для основных кейсов. Тестируется на Python 3.10, 3.13, 3.14 и разных версиях aiogram (от 3.0.0 до 3.24).

В планах:
- Публикация на PyPI
- Расширение поддержки мидлварей
- Поддержка webhook-режима для обеих платформ
- Поддержка дополнительных платформ (архитектура это позволяет)

## Попробуй

Весь код открыт: [github.com/Korean-DOG/obabot](https://github.com/Korean-DOG/obabot)

В репозитории есть директория `examples/` с полными рабочими примерами:
- `aiogram_original.py` → `aiogram_migrated.py` — миграция шаг за шагом
- `telegram_only.py`, `max_only.py` — однопплатформенные боты
- `dual_platform.py` — бот на две платформы с FSM и клавиатурами
- `test_mode_example.py` — как тестировать без токенов

Если что-то не работает или чего-то не хватает — кидай issue. Если работает — кинь звёздочку, мне будет приятно.

---

*Автор: Alexander Alekseev*
*GitHub: [Korean-DOG/obabot](https://github.com/Korean-DOG/obabot)*
