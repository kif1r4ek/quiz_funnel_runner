# Отчёт об изменениях: 6.5 Plugin Architecture

Дата: 2026-03-10

---

## Зачем переходить на плагинную архитектуру

### Проблема монолитного подхода

До перехода каждый новый тип экрана требовал трёх правок в трёх разных местах: написать класс
в `strategies/`, зарегистрировать его руками в `main.py`, не забыть добавить имя в хардкод
`SCREEN_TYPES` в `screenshotter.py`. Это классическая ловушка: чем больше типов экранов, тем
выше вероятность рассинхронизации — один разработчик добавляет класс и забывает зарегистрировать,
другой регистрирует не в том порядке. Код о порядке приоритетов был разбросан, а не
сосредоточен в одном месте.

Кроме того, `strategies/` и `main.py` были жёстко связаны: нельзя было добавить плагин, не
трогая ядро системы. Это нарушает принцип открытости/закрытости (OCP) — система должна быть
открыта для расширения, но закрыта для модификации.

### Что даёт плагинная архитектура

**Масштабируемость без правок ядра.**
Чтобы добавить поддержку нового типа экрана (например, `video_upsell`, `social_proof`,
`age_gate`) достаточно создать один файл `plugins/video_upsell.py` с функцией
`create_plugin(ctx)`. Ядро системы — `loader.py`, `runner.py`, `main.py` — не трогается
вообще. При следующем запуске новый плагин подхватится автоматически.

**Независимость плагинов.**
Каждый плагин — изолированный модуль. Он знает только о своей задаче: как распознать экран и
что с ним сделать. Он не знает о существовании других плагинов. Это означает, что сломанный
плагин не тянет за собой всю систему: загрузчик поймает исключение, выведет предупреждение и
продолжит загрузку остальных.

**Приоритеты как единственный механизм порядка.**
Раньше порядок определялся тем, в какую позицию в `main.py` ты поставил `registry.register()`.
Это неявная зависимость от порядка кода. Теперь порядок задаётся явным числом `priority` прямо
в плагине. Хочешь, чтобы твой плагин проверялся раньше `question` (priority 600)? Ставь
priority 650. Это читаемо, предсказуемо и не требует открывать `main.py`.

**Тестируемость на уровне плагина.**
Каждый плагин можно тестировать отдельно через его фабрику `create_plugin(ctx)` с нужным
контекстом. Не нужно поднимать весь реестр или мокать `main.py`.

**Контекст как механизм конфигурации.**
`PluginContext` передаётся в `create_plugin(ctx)` при загрузке. Это означает, что один и тот
же плагин может работать с разными наборами данных (`defaults`) в зависимости от запуска —
например, для A/B тестирования разных email-адресов или имён пользователя — без изменения
кода плагина.

**Команда без конфликтов.**
При работе нескольких разработчиков каждый работает в своём файле-плагине. Никаких
конфликтов в `main.py` при слиянии веток — каждый добавляет только свой файл.

### Что это значит конкретно для данного проекта

Сейчас в `plugins/` живут 8 встроенных плагинов, покрывающих все известные типы экранов
quiz-воронок. Но реальные воронки постоянно меняются: сайты добавляют новые виды экранов,
A/B тесты, нестандартные блоки. С плагинной архитектурой реакция на это — это дело
одного файла, а не рефакторинга. Нашёл новый тип экрана на сайте — написал плагин,
положил в папку, перезапустил. Готово.

---

## 1. Выполненная цель

Проект полностью переведён на самодостаточную плагинную архитектуру.

**Фаза 1 (первоначальная):** переключён bootstrap с ручной регистрации на `load_plugins()`;
плагины-обёртки подключали существующие реализации из `strategies/*` через `StrategyPluginAdapter`.

**Фаза 2 (финальная):** каждый плагин стал полностью самодостаточным; слой `strategies/`
полностью удалён; исправлены архитектурные ошибки.

Важно: изменения, связанные с Forex, не выполнялись и не затрагивались.

---

## 2. Архитектурные изменения — Фаза 1

### 2.1. Добавлено ядро плагинов

Созданы модули:
- `plugins/base.py`
- `plugins/context.py`
- `plugins/loader.py`
- `plugins/__init__.py`

Реализовано:
- Контракт плагина: `name`, `priority`, `can_handle(page)`, `execute(page)`.
- Фабричный интерфейс: каждый плагин экспортирует `create_plugin(ctx)`.
- `PluginContext` с полем `defaults`.
- Динамическая загрузка top-level `*.py` из `PLUGINS_DIR` без рекурсии.
- Исключение служебных файлов из загрузки (`__init__`, `base`, `loader`, `context`).
- Политика ошибок `skip + warning` для невалидных/падающих плагинов.
- Стабильная сортировка: `priority DESC`, затем `name ASC`, затем `filename ASC`.
- Обработка коллизий `name`: сохраняется первый плагин, дубликаты пропускаются с warning.

### 2.2. Добавлены built-in плагины экранов (обёртки)

Созданы плагины:
- `plugins/checkout.py` (priority `1000`)
- `plugins/paywall.py` (priority `900`)
- `plugins/email.py` (priority `800`)
- `plugins/input.py` (priority `700`)
- `plugins/question.py` (priority `600`)
- `plugins/chart.py` (priority `500`)
- `plugins/info.py` (priority `400`)
- `plugins/other.py` (priority `0`)

На данном этапе плагины делегировали логику в `strategies/*` через `StrategyPluginAdapter`.

### 2.3. Переключён bootstrap на плагины

Обновлён `main.py`:
- Убрана ручная регистрация `registry.register(...)`.
- Добавлен `build_registry_from_plugins(ctx, plugins_dir)`.
- Реестр строится только из загруженных плагинов.
- Если валидных плагинов нет, выбрасывается ошибка запуска.
- Сохранён legacy-алиас `build_registry()` для переходной совместимости.

### 2.4. Изменения конфигурации

Обновлён `config.py`:
- Добавлен параметр `PLUGINS_DIR: str = "plugins"`.

---

## 3. Архитектурные изменения — Фаза 2 (финальная миграция)

### 3.1. Каждый плагин стал полностью самодостаточным

Вся логика обнаружения и выполнения перенесена из `strategies/*` непосредственно в
соответствующий файл плагина. `StrategyPluginAdapter` и импорты `strategies.*` удалены из всех
плагинов.

| Плагин | Что изменилось |
|---|---|
| `plugins/paywall.py` | встроена логика детекции paywall-экрана |
| `plugins/checkout.py` | встроена логика детекции checkout-экрана |
| `plugins/chart.py` | встроена логика детекции chart/progress-экрана |
| `plugins/info.py` | встроена логика детекции info-экрана |
| `plugins/other.py` | встроена fallback-логика |
| `plugins/question.py` | встроена вся логика выбора ответа (JS-хелперы, a11y, клики) |
| `plugins/email.py` | встроена логика заполнения e-mail + consent-чекбоксов; **теперь использует `ctx.defaults`** вместо прямого импорта `DEFAULTS` из `config` |
| `plugins/input.py` | встроена логика заполнения полей ввода; **теперь использует `ctx.defaults`** вместо прямого импорта `DEFAULTS` из `config` |

Исправленная ошибка: `email` и `input` плагины игнорировали `PluginContext.defaults` и читали
`DEFAULTS` напрямую из `config`, что делало контекст бесполезным.

### 3.2. Удалён `StrategyPluginAdapter`

Из `plugins/base.py` удалён класс `StrategyPluginAdapter` и импорт `BaseStrategy`.
Файл теперь содержит только `ScreenPlugin` Protocol.

Из `plugins/__init__.py` убран экспорт `StrategyPluginAdapter`.

### 3.3. `StrategyRegistry` перенесён в `plugins/registry.py`

Реестр `StrategyRegistry` переехал из `strategies/registry.py` в `plugins/registry.py`.
Интерфейс не изменился: `register(handler)`, `resolve(page) -> handler`.

`plugins/loader.py` — добавлен `"registry"` в `_SERVICE_MODULES`, чтобы файл реестра не
сканировался как плагин.

`plugins/__init__.py` — добавлен экспорт `StrategyRegistry`.

`main.py` — обновлён импорт: `from plugins.registry import StrategyRegistry`.

### 3.4. Удалена папка `strategies/`

Папка `strategies/` полностью удалена. Были удалены:
- `strategies/base.py`
- `strategies/registry.py`
- `strategies/utils.py`
- `strategies/chart_strategy.py`
- `strategies/checkout_strategy.py`
- `strategies/email_strategy.py`
- `strategies/info_strategy.py`
- `strategies/input_strategy.py`
- `strategies/other_strategy.py`
- `strategies/paywall_strategy.py`
- `strategies/question_strategy.py`
- `strategies/__init__.py`

### 3.5. Создан `utils.py`

Общие DOM-хелперы вынесены в `utils.py` (корень проекта):
- `visible_count(locator, max_items) -> int`
- `safe_body_text(page) -> str`

Обновлён `runner.py`: `from strategies.utils import safe_body_text` → `from utils import safe_body_text`.

### 3.6. Обновлён `screenshotter.py`

Убран хардкод `SCREEN_TYPES`. Директории для классифицированных скриншотов создаются
динамически в `save_step()` по мере появления новых типов экранов от плагинов.
`ensure_base_dirs()` теперь создаёт только `results_dir` и `_classified/`.

---

## 4. Тестовые изменения

### 4.1. Добавлены тесты плагинной архитектуры (Фаза 1)

Создан файл `tests/test_plugins_loader.py`:
- Проверка загрузки и порядка built-in плагинов.
- Проверка сортировки по приоритету/имени.
- Проверка soft-fail при ошибках импорта и невалидном контракте.
- Проверка дедупликации по `plugin.name`.
- Проверка автоподключения custom plugin без правок `main.py`.

### 4.2. Обновлён `test_paywall.py` (Фаза 2)

Импорт изменён: `from strategies.paywall_strategy import PaywallStrategy`
→ `from plugins.paywall import create_plugin`.

Тест теперь проверяет `PaywallPlugin` через его фабрику `create_plugin(ctx)`.

### 4.3. Обновлён `test_registry.py` (Фаза 2)

Импорт изменён: `from strategies.registry import StrategyRegistry`
→ `from plugins.registry import StrategyRegistry`.

Тестовые двойники больше не наследуют `BaseStrategy` — используются plain-объекты
с нужным контрактом (`name`, `can_handle`, `execute`).

### 4.4. Обновлён `test_playwright_smoke.py` (обе фазы)

- Фаза 1: корректный `skip` при отсутствии пакета `playwright`.
- Фаза 2: убраны прямые импорты из `strategies`; реестр строится через
  `build_registry_from_plugins(PluginContext(defaults={}))`.

---

## 5. Проверки после внедрения

Выполнено:
```
python -m unittest discover -s tests -v
```

Результат (Фаза 2):
```
Ran 10 tests in 15.9s — OK
```

Все тесты прошли, включая Playwright smoke-тест.

---

## 6. Итоговый список затронутых файлов

### Добавлены
- `utils.py`
- `plugins/__init__.py`
- `plugins/base.py`
- `plugins/context.py`
- `plugins/loader.py`
- `plugins/registry.py`
- `plugins/checkout.py`
- `plugins/paywall.py`
- `plugins/email.py`
- `plugins/input.py`
- `plugins/question.py`
- `plugins/chart.py`
- `plugins/info.py`
- `plugins/other.py`
- `tests/test_plugins_loader.py`
- `CHANGES_6_5_PLUGIN_ARCHITECTURE.md`

### Изменены
- `main.py`
- `config.py`
- `runner.py`
- `screenshotter.py`
- `tests/test_paywall.py`
- `tests/test_registry.py`
- `tests/test_playwright_smoke.py`

### Удалены
- `strategies/` (вся папка со всеми файлами)

---

## 7. Итог

Миграция на Plugin Architecture завершена полностью:

- Каждый тип экрана — отдельный самодостаточный плагин в `plugins/`.
- Программа сканирует папку и подключает плагины автоматически.
- Порядок обработки управляется приоритетами (`priority`).
- Ошибки в отдельных плагинах не останавливают систему.
- `PluginContext.defaults` теперь реально используется плагинами `email` и `input`.
- Слой `strategies/` полностью удалён — никаких переходных обёрток не осталось.
- Добавить новый тип экрана = создать один `.py` файл в `plugins/` с `create_plugin(ctx)`.
