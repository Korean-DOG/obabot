# Настройка секретов для тестов

Для запуска тестов в GitHub Actions необходимо добавить тестовые токены в секреты репозитория.

## Шаги настройки

1. Перейдите в настройки репозитория: **Settings** → **Secrets and variables** → **Actions**

2. Добавьте следующие секреты:

   - **TG_TEST_TOKEN** - токен Telegram бота для тестирования
   - **MAX_TEST_TOKEN** - токен Max бота для тестирования

3. Нажмите **New repository secret** для каждого токена

## Получение тестовых токенов

### Telegram
1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Получите токен командой `/newbot`
3. Используйте этот токен как `TG_TEST_TOKEN`

### Max
1. Перейдите на [developers.max.ru](https://developers.max.ru)
2. Создайте приложение и бота
3. Получите токен бота
4. Используйте этот токен как `MAX_TEST_TOKEN`

## Структура тестов в CI

GitHub Actions запускает тесты параллельно для максимальной скорости:

```
┌─────────────────────────────────────────────────────────────┐
│                      Unit Tests                              │
│  (Python 3.10, 3.13, 3.14 - параллельно)                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌───────────────────┐     ┌───────────────────┐
│   E2E Telegram    │     │     E2E Max       │
│   (параллельно)   │     │   (параллельно)   │
└─────────┬─────────┘     └─────────┬─────────┘
          │                         │
          └───────────┬─────────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │  Integration Tests  │
            │  (требуют токены)   │
            └─────────────────────┘
```

### Jobs в CI

| Job | Описание | Зависимости |
|-----|----------|-------------|
| `unit-tests` | Быстрые unit тесты без внешних зависимостей | - |
| `e2e-telegram` | E2E тесты для Telegram | `unit-tests` |
| `e2e-max` | E2E тесты для Max | `unit-tests` |
| `compatibility` | Тесты совместимости с разными версиями aiogram | `unit-tests` |
| `integration` | Интеграционные тесты с реальными API | `e2e-telegram`, `e2e-max` |

## Тесты без токенов

Если токены не указаны:
- **Unit тесты** — выполняются полностью
- **E2E тесты** — выполняются с симулированными payload'ами
- **Integration тесты** — пропускаются (skip)

## Локальный запуск тестов

```bash
# Все тесты
pytest tests/ -v

# Только unit тесты
pytest tests/ -v --ignore=tests/test_e2e_migration.py --ignore=tests/test_integration.py

# Только E2E тесты для Telegram
pytest tests/test_e2e_migration.py -v -k "telegram"

# Только E2E тесты для Max
pytest tests/test_e2e_migration.py -v -k "max"

# Тесты для обеих платформ
pytest tests/test_e2e_migration.py -v -k "dual"
```

## Маркеры тестов

| Маркер | Описание |
|--------|----------|
| `@pytest.mark.e2e` | End-to-end тесты |
| `@pytest.mark.telegram` | Тесты для Telegram |
| `@pytest.mark.max` | Тесты для Max |
| `@pytest.mark.dual` | Тесты для обеих платформ |
| `@pytest.mark.integration` | Тесты с реальными API |
