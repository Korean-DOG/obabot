# obabot

**Универсальная асинхронная библиотека для ботов Telegram, Max и Yandex Messenger с API, совместимым с aiogram.**

Напишите код бота один раз, запустите его на Telegram, Max, Yandex Messenger или на всех платформах одновременно!

## Возможности

* **Минимальные изменения при миграции** — меняются только импорты и инициализация
* **API, совместимый с aiogram** — используйте знакомые декораторы, фильтры и FSM
* **Поддержка нескольких платформ** — работайте на Telegram, Max, Yandex Messenger или на всех одновременно
* **Нативная производительность для Telegram** — без накладных расходов (прямой aiogram)
* **Прозрачные адаптеры для Max и Yandex** — API платформ автоматически преобразуется в интерфейс, похожий на aiogram
* **Веб-интерфейс и PWA** — FastAPI-слой и устанавливаемое мобильное приложение через `obabot[web]`
* **Ленивая загрузка платформ** — aiogram/umaxbot/httpx импортируются только при первом событии

## Установка

```bash
pip install obabot
```

### Дополнительные зависимости

```bash
# Для поддержки Yandex Messenger
pip install obabot[yandex]

# Для веб-интерфейса и PWA
pip install obabot[web]

# Для fsm-voyager интеграции
pip install obabot[voyager]

# Всё сразу (включая dev-зависимости)
pip install obabot[all]
```

### Зависимости для платформ

После установки obabot необходимо установить библиотеки для платформ:

```bash
# Для поддержки Telegram
pip install aiogram>=3.0.0

# Для поддержки Max
pip install umaxbot>=0.1.7

# Для поддержки Yandex Messenger (httpx уже включён)
pip install obabot[yandex]

# Все платформы
pip install aiogram>=3.0.0 umaxbot>=0.1.7 httpx>=0.24.0
```

**Рекомендуемая версия aiogram:** `3.24` (последняя стабильная версия 3.x, используется в тестах)

## Быстрый старт

### Только Telegram

```python
from obabot import create_bot
from obabot.filters import Command

bot, dp, router = create_bot(tg_token="ВАШ_ТЕЛЕГРАМ_ТОКЕН")

@router.message(Command("start"))
async def start(message):
    await message.answer(f"Привет с {message.platform}!")

await dp.start_polling(bot)
```

### Только Max

```python
from obabot import create_bot
from obabot.filters import Command

# Просто измените аргумент токена!
bot, dp, router = create_bot(max_token="ВАШ_МАКС_ТОКЕН")

@router.message(Command("start"))
async def start(message):
    await message.answer(f"Привет с {message.platform}!")

await dp.start_polling(bot)
```

### Только Yandex Messenger

```python
from obabot import create_bot
from obabot.filters import Command

bot, dp, router = create_bot(yandex_token="ВАШ_ЯНДЕКС_ТОКЕН")

@router.message(Command("start"))
async def start(message):
    await message.answer(f"Привет с {message.platform}!")

await dp.start_polling(bot)
```

### Две платформы (двойной режим)

```python
from obabot import create_bot
from obabot.filters import Command

bot, dp, router = create_bot(
    tg_token="ВАШ_ТЕЛЕГРАМ_ТОКЕН",
    max_token="ВАШ_МАКС_ТОКЕН"
)

@router.message(Command("start"))
async def start(message):
    await message.answer(f"Привет с {message.platform.upper()}!")

await dp.start_polling(bot)
```

### Три платформы

```python
from obabot import create_bot
from obabot.filters import Command

bot, dp, router = create_bot(
    tg_token="ВАШ_ТЕЛЕГРАМ_ТОКЕН",
    max_token="ВАШ_МАКС_ТОКЕН",
    yandex_token="ВАШ_ЯНДЕКС_ТОКЕН",
)

@router.message(Command("start"))
async def start(message):
    await message.answer(f"Привет с {message.platform}!")

await dp.start_polling(bot)
```

## Миграция с aiogram

Миграция существующего бота на aiogram очень проста — просто измените импорты и инициализацию!

### До (aiogram)

```python
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

bot = Bot(token="TOKEN")
dp = Dispatcher()
router = Router()
dp.include_router(router)

@router.message(Command("start"))
async def start(message):
    await message.answer("Привет!")

await dp.start_polling(bot)
```

### После (obabot)

```python
from obabot import create_bot
from obabot.filters import Command
from obabot.fsm import State, StatesGroup, FSMContext

bot, dp, router = create_bot(tg_token="TOKEN")

@router.message(Command("start"))
async def start(message):
    await message.answer("Привет!")

await dp.start_polling(bot)
```

**Изменения:**

* ✅ Изменены импорты: `aiogram` → `obabot`
* ✅ Изменена инициализация: `Bot/Dispatcher/Router` → `create_bot()`
* ✅ **Всё остальное на 100% идентично!**

См. `examples/aiogram_original.py` и `examples/aiogram_migrated.py` для полного примера миграции.

## Справочник API

### `create_bot()`

Основная фабричная функция для создания бота.

```python
def create_bot(
    tg_token: str | None = None,
    max_token: str | None = None,
    yandex_token: str | None = None,
    fsm_storage: BaseStorage | None = None,
    test_mode: bool | None = None,
) -> tuple[ProxyBot | StubBot, ProxyDispatcher | Dispatcher, ProxyRouter | Router]:
    ...
```

**Аргументы:**

* `tg_token` - токен Telegram бота (опционально; в тестовом режиме не требуется)
* `max_token` - токен Max бота (опционально; в тестовом режиме не требуется)
* `yandex_token` - токен Yandex Messenger бота (опционально; в тестовом режиме не требуется)
* `fsm_storage` - хранилище для FSM состояний (опционально). Будет использоваться всеми платформами.
* `test_mode` - если `True`, включается тестовый режим (без токенов и сетевых вызовов). Если `None`, используется переменная окружения `TESTING=1`.

**Возвращает:** Кортеж `(bot, dispatcher, router)`

**Режимы:**

* Только `tg_token` → режим Telegram
* Только `max_token` → режим Max
* Только `yandex_token` → режим Yandex Messenger
* Любая комбинация токенов → мультиплатформенный режим
* `test_mode=True` или `TESTING=1` → тестовый режим

### Обработчики

Используйте те же декораторы, что и в aiogram:

```python
# Вариант 1: Использование router (рекомендуется)
@router.message(Command("start"))
async def cmd_start(message):
    await message.answer("Привет!")

# Вариант 2: Использование dispatcher (тоже работает, как в aiogram)
@dp.message(Command("start"))
async def cmd_start_v2(message):
    await message.answer("Привет!")

# Оба работают с фильтрами
@router.message(F.text)
async def text_handler(message):
    await message.answer(f"Вы сказали: {message.text}")

@router.callback_query(F.data == "button")
async def callback_handler(callback):
    await callback.answer("Кнопка нажата!")
    await callback.message.edit_text("Обновлено!")
```

### Объект Message

Все сообщения имеют эти свойства (как в aiogram):

```python
message.text          # Текст сообщения
message.from_user     # Пользователь, отправивший сообщение
message.chat          # Объект чата
message.message_id    # ID сообщения
message.platform      # "telegram", "max" или "yandex"

# Методы
await message.answer("Текст ответа")
await message.reply("Ответить на это сообщение")
await message.delete()
await message.edit_text("Новый текст")
```

### FSM (Конечный автомат состояний)

```python
from obabot.fsm import State, StatesGroup, FSMContext

class Form(StatesGroup):
    name = State()
    age = State()

@router.message(Command("start"))
async def start(message, state: FSMContext):
    await state.set_state(Form.name)
    await message.answer("Как тебя зовут?")

@router.message(Form.name)
async def process_name(message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.age)
    await message.answer("Сколько тебе лет?")
```

### Клавиатуры

```python
from obabot.types import InlineKeyboardMarkup, InlineKeyboardButton

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Кнопка 1", callback_data="btn1"),
        InlineKeyboardButton(text="Кнопка 2", callback_data="btn2"),
    ]
])

await message.answer("Выберите:", reply_markup=keyboard)
```

### Фильтры

```python
from obabot.filters import Command, F, StateFilter

@router.message(Command("start", "help"))  # Несколько команд
@router.message(F.text.startswith("!"))     # Магический фильтр
@router.message(F.photo)                   # Сообщения с фото
@router.callback_query(F.data == "click") # Callback data
```

## Веб-интерфейс и мобильное приложение (PWA)

obabot позволяет добавить веб-API и устанавливаемое мобильное приложение к уже работающему боту — без изменения обработчиков.

### Установка зависимостей

```bash
pip install obabot[web]
```

### Веб-API (create_web)

`create_web` создаёт FastAPI-приложение, которое принимает HTTP-запросы и прогоняет их через те же обработчики, что работают в Telegram / Max.

```python
from obabot import create_bot
from obabot.web import create_web

bot, dp, router = create_bot(tg_token="TOKEN")

@router.message()
async def echo(message):
    await message.answer(f"Эхо: {message.text}")

web_app = create_web(dp, base_path="/api")
```

**Эндпоинты:**

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/webhook` | Отправить текстовое сообщение (`user_id`, `text`) |
| POST | `/api/callback` | Нажать кнопку (`user_id`, `callback_data`) |
| GET | `/api/state/{user_id}` | Получить FSM-состояние и данные |
| POST | `/api/reset/{user_id}` | Сбросить FSM-состояние |

**Пример запроса:**

```bash
curl -X POST http://localhost:8000/api/webhook \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "text": "/start"}'
```

**JWT-аутентификация (опционально):**

```python
web_app = create_web(dp, auth_config={"secret_key": "my-secret"})
```

### Мобильное приложение (create_mobile)

`create_mobile` добавляет PWA-поддержку: manifest.json, service worker и минимальный чат-интерфейс, который можно установить на домашний экран.

```python
from obabot.web import create_web, create_mobile

web_app = create_web(dp)
mobile_app = create_mobile(
    web_app,
    name="Мой бот",
    short_name="Бот",
    icons="/static/icons/",
    theme_color="#4a76a8",
)
```

### Запуск вместе с polling

```python
import asyncio
import uvicorn

async def main():
    bot_task = asyncio.create_task(dp.start_polling(bot))
    config = uvicorn.Config(mobile_app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()
    await bot_task

asyncio.run(main())
```

После этого:
- Бот доступен через Telegram, Max, Yandex Messenger **и** HTTP API
- Откройте `http://localhost:8000/` — вы увидите чат-интерфейс
- На мобильном устройстве браузер предложит «Установить приложение»

См. `examples/web_demo.py` для полного примера.

## Архитектура

```
obabot/
├── obabot/
│   ├── __init__.py          # create_bot, BPlatform
│   ├── factory.py           # Реализация create_bot()
│   ├── detection.py         # Автоопределение платформы по IP / payload
│   ├── proxy/               # Proxy классы для мультиплексирования
│   │   ├── bot.py           # ProxyBot
│   │   ├── dispatcher.py    # ProxyDispatcher
│   │   └── router.py        # ProxyRouter
│   ├── adapters/            # Адаптеры платформ → aiogram-интерфейс
│   │   ├── message.py       # MaxMessageAdapter
│   │   ├── max_callback.py  # MaxCallbackQuery
│   │   ├── telegram_callback.py # TelegramCallbackQuery
│   │   ├── yandex_message.py    # YandexMessageAdapter
│   │   ├── yandex_callback.py   # YandexCallbackQuery
│   │   ├── yandex_user.py       # YandexUserAdapter, YandexChatAdapter
│   │   ├── user.py          # MaxUserAdapter, MaxChatAdapter
│   │   └── keyboard.py      # Конвертер клавиатур (Max + Yandex)
│   ├── platforms/           # Реализации платформ
│   │   ├── base.py          # BasePlatform ABC
│   │   ├── telegram.py      # TelegramPlatform (нативный aiogram)
│   │   ├── max.py           # MaxPlatform (адаптированный umaxbot)
│   │   ├── yandex.py        # YandexPlatform (HTTP Bot API)
│   │   └── lazy.py          # LazyPlatform (отложенная загрузка)
│   ├── web/                 # Веб-слой и PWA (опционально, obabot[web])
│   │   ├── __init__.py      # create_web, create_mobile
│   │   ├── api.py           # Создание FastAPI-приложения
│   │   ├── pwa.py           # PWA-поддержка (manifest, service worker)
│   │   ├── dispatch.py      # Маршрутизация запросов через обработчики
│   │   ├── emulators.py     # WebBot, WebMessage, WebCallbackQuery
│   │   └── auth.py          # JWT-аутентификация
│   ├── middleware/           # Middleware-слой
│   │   └── fsm_coverage.py  # Логирование FSM-переходов для voyager
│   ├── voyager/             # Интеграция с fsm-voyager
│   │   ├── chain_analyzer.py # Анализ цепочек навигации
│   │   ├── bridge.py        # Мост к fsm-voyager
│   │   └── tracker.py       # Трекер цепочек
│   ├── filters.py           # Реэкспортированные фильтры aiogram
│   ├── fsm.py               # Реэкспортированные компоненты FSM
│   └── types.py             # Enum BPlatform, реэкспорты типов
├── examples/
│   ├── aiogram_original.py      # Оригинальный бот на aiogram
│   ├── aiogram_migrated.py      # Мигрированный на obabot
│   ├── telegram_only.py         # Telegram с FSM и клавиатурами
│   ├── max_only.py              # Max с FSM и клавиатурами
│   ├── yandex_only.py           # Yandex Messenger
│   ├── dual_platform.py         # Две платформы одновременно
│   ├── triple_platform.py       # Три платформы (Telegram + Max + Yandex)
│   └── web_demo.py              # Telegram + Max + Web PWA
└── tests/
    ├── test_basic.py            # Базовые тесты
    ├── test_detection.py        # Тесты автоопределения платформ
    ├── test_yandex.py           # Тесты Yandex-адаптеров и платформы
    ├── test_web.py              # Тесты веб-слоя и PWA
    ├── test_chain_tracking.py   # Тесты voyager-анализа
    └── ...
```

### Как это работает

1. **Telegram (нативный)**: Сообщения проходят напрямую к обработчикам aiogram. Добавляется только атрибут `message.platform`.
2. **Max (адаптированный)**: Сообщения оборачиваются в `MaxMessageAdapter`, который предоставляет интерфейс, совместимый с aiogram.
3. **Yandex Messenger (HTTP)**: Используется лёгкий HTTP-клиент (`YandexBot`) к Yandex Bot API. Сообщения оборачиваются в `YandexMessageAdapter`.
4. **Мультиплатформенный режим**: Все платформы работают параллельно. Каждый обработчик регистрируется на всех платформах.
5. **Ленивая загрузка**: Библиотеки платформ (aiogram, umaxbot, httpx) импортируются только при первом событии от этой платформы — для минимального времени холодного старта.
6. **Веб/PWA**: FastAPI-приложение (`create_web`) принимает HTTP-запросы и прогоняет их через те же обработчики, что работают в мессенджерах. `create_mobile` добавляет PWA-манифест и чат-интерфейс.

## Примеры

См. директорию `examples/` для полных рабочих примеров:

* **`aiogram_original.py`** - Полный пример бота на оригинальном aiogram 3.x
* **`aiogram_migrated.py`** - Тот же бот, мигрированный на obabot
* **`telegram_only.py`** - Бот для Telegram с FSM и клавиатурами
* **`max_only.py`** - Тот же бот для Max
* **`yandex_only.py`** - Бот для Yandex Messenger
* **`dual_platform.py`** - Бот для двух платформ одновременно
* **`triple_platform.py`** - Бот для трёх платформ (Telegram + Max + Yandex)
* **`test_mode_example.py`** - Пример тестового режима
* **`web_demo.py`** - Telegram + Max + Web PWA на одном диспетчере

## Тестирование

Библиотека тестируется на разных версиях Python и aiogram:

* **Python:** 3.10, 3.13, 3.14
* **aiogram:** 3.0.0, 3.24, default (>=3.0.0)

```bash
# Установка dev-зависимостей
pip install -e ".[dev]"

# Запуск тестов
pytest

# С покрытием
pytest --cov=obabot --cov-report=html
```

## Лицензия

Proprietary License - см. файл LICENSE для деталей.

## Вклад в проект

Вклад приветствуется! Пожалуйста, не стесняйтесь создавать issues и pull requests.
