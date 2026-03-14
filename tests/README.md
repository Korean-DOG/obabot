# Tests for obabot

## Running Tests

### Local Testing

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=obabot --cov-report=html

# Run specific test file
pytest tests/test_basic.py

# Run with verbose output
pytest -v
```

### With Test Tokens

To run integration tests that require real API tokens:

```bash
export TG_TOKEN="your_telegram_token"
export MAX_TOKEN="your_max_token"
pytest tests/ -v
```

Or use `.env` file:
```
TG_TOKEN=your_telegram_token
MAX_TOKEN=your_max_token
```

## Test Structure

- **`test_test_mode.py`** - Тесты тестового режима (`test_mode=True` / `TESTING=1`): без токенов и сети, запускаются в CI без секретов
- **`test_basic.py`** - Базовые тесты создания ботов, свойств и совместимости API
- **`test_handlers.py`** - Тесты регистрации handlers и их выполнения с моками
- **`test_router_handlers.py`** - Глубокие тесты всех типов handlers (15 типов), делегирования dp→router, выполнения handlers
- **`test_bot_methods.py`** - Тесты существования всех методов отправки (26+ методов)
- **`test_compatibility.py`** - Тесты совместимости API с aiogram (импорты, декораторы, FSM)
- **`test_dispatcher.py`** - Тесты функциональности dispatcher (polling, middleware, workflow_data)
- **`test_integration.py`** - Интеграционные тесты с реальными токенами (get_me, platform detection)
- **`test_aiogram_comparison.py`** - Сравнение поведения obabot с оригинальным aiogram (side-by-side)

## Тестовый режим (test mode)

Тесты тестового режима (`tests/test_test_mode.py`) не требуют реальных токенов и не обращаются к сети. Их можно запускать всегда, в т.ч. в CI без секретов:

```bash
pytest tests/test_test_mode.py -v
```

Библиотеки для тестирования (например, `aiogram-test-framework`, `pytest`, `pytest-asyncio`) **не входят в зависимости obabot** — их устанавливает у себя пользователь, когда пишет тесты. В репозитории obabot для своих тестов используются только pytest и pytest-asyncio (опциональная зависимость `[dev]`). **aiogram-test-framework в CI не ставится и не используется** — тесты тестового режима лишь проверяют, что `create_bot(test_mode=True)` возвращает нужные объекты и что роутер можно подключить к другому диспетчеру; сам фреймворк пользователь ставит у себя при необходимости.

## CI/CD

Тесты автоматически запускаются на GitHub Actions для следующих конфигураций:

- **Unit-тесты** — Python 3.10, 3.13, 3.14 (без секретов)
- **Test mode** — тесты тестового режима (`test_test_mode.py` + тесты test_mode в `test_basic.py`) на Python 3.10 и 3.13, **без токенов и секретов**
- **Python 3.10** + **aiogram 3.0.0** (минимальная поддерживаемая версия)
- **Python 3.13** + **aiogram 3.24** (последняя стабильная версия 3.x)
- **Python 3.14** + **aiogram default** (>=3.0.0, последняя доступная версия)

Тесты также можно запустить вручную через `workflow_dispatch` в GitHub Actions.

## Test Tokens

For CI/CD, add these secrets to your GitHub repository:
- `TG_TEST_TOKEN` - Telegram bot token for testing
- `MAX_TEST_TOKEN` - Max bot token for testing

Settings → Secrets and variables → Actions → New repository secret

