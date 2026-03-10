# Quiz Funnel Runner

Автоматический обход квиз-воронок с помощью Playwright. Бот проходит воронку пошагово: классифицирует тип экрана через динамически загружаемые плагины (`plugins/*.py`), а при зависании переключается на LLM (Ollama или OpenRouter).

## Как это работает

**Порядок действий на каждом шаге:**
1. **DOM-плагин** — классифицирует экран и выполняет действие через CSS-селекторы и JS
2. **LLM-фоллбек** — включается только при зависании (одинаковый контент 2+ шага подряд)
   - Ollama (локально, бесплатно, без ограничений) → пробуется первой, если включена
   - OpenRouter (облако, бесплатный тариф) → резерв, если Ollama недоступна

## Архитектура

```
main.py               Точка входа — запускает браузер, запускает все воронки
plugins/              Плагинная архитектура экранов (автосканирование *.py)
runner.py             Главный цикл — выбирает стратегию, отслеживает зависания, вызывает LLM
config.py             Все настройки (воронки, таймауты, ключи LLM)
actions.py            Общие DOM-хелперы — click_continue, fill_detected_inputs
popup_handler.py      Закрытие cookie/согласительных баннеров
screenshotter.py      Снятие скриншотов и запись лога на каждом шаге
llm_fallback.py       LLM-интеграция — OllamaVision + OpenRouterVision

plugins/
  loader.py           Динамический загрузчик плагинов (create_plugin(ctx))
  context.py          PluginContext (минимум defaults)
  checkout.py         Built-in plugin (priority 1000)
  paywall.py          Built-in plugin (priority 900)
  email.py            Built-in plugin (priority 800)
  input.py            Built-in plugin (priority 700)
  question.py         Built-in plugin (priority 600)
  chart.py            Built-in plugin (priority 500)
  info.py             Built-in plugin (priority 400)
  other.py            Built-in plugin (priority 0)

strategies/
  ...                 Legacy compatibility layer (переходный период)
```

## Приоритет built-in plugins

1. **Checkout** — форма оплаты → стоп
2. **Paywall** — тарифы / подписка → стоп
3. **Email** — поле email + чекбоксы приватности → заполнить + продолжить
4. **Input** — текстовые/числовые/range/select поля → заполнить + продолжить
5. **Question** — радио-кнопки / карточки ответов → кликнуть случайный + продолжить
6. **Chart** — canvas / SVG с результатом → продолжить
7. **Info** — текст с активной кнопкой «Продолжить» → продолжить
8. **Other** — фоллбек: кликнуть любую не-навигационную кнопку

`strategies/*` сохранены как compatibility layer. Новый основной путь расширения — добавление файлов в `plugins/`.

## Настройки (`config.py`)

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `FUNNELS` | список URL | Воронки для обхода |
| `DEFAULTS` | name/height/weight/age/email/phone | Значения для заполнения полей |
| `PLUGINS_DIR` | `"plugins"` | Директория автозагрузки плагинов |
| `DEVICE_NAME` | `"iPhone 12"` | Эмуляция устройства Playwright |
| `HEADLESS` | `False` | Запуск браузера без интерфейса |
| `MAX_STEPS` | `120` | Максимум шагов на воронку |
| `TIMEOUT` | `20000` | Таймаут загрузки страницы (мс) |
| `STEP_DELAY` | `2000` | Пауза между шагами (мс) |
| `STUCK_LIMIT` | `3` | Шагов с одинаковым контентом до сдачи |
| `LLM_ENABLED` | `True` | Включить LLM-фоллбек |
| `LLM_PRIMARY` | `False` | LLM ведёт каждый шаг (DOM — резерв) |
| `OLLAMA_ENABLED` | `True` | Включить локальный бэкенд Ollama |
| `OLLAMA_MODEL` | `"llava:7b"` | Vision-модель Ollama (~4.7 ГБ RAM) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL API Ollama |
| `OPENROUTER_API_KEY` | — | Ключ API OpenRouter (из `.env`) |
| `OPENROUTER_MODEL` | `mistralai/mistral-small-3.1-24b-instruct:free` | Бесплатная vision-модель |

Секреты хранятся в `.env` (не попадает в git). Пример — в `.env.example`.

## Установка и запуск

```bash
# 1. Создать виртуальное окружение и установить зависимости
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Установить браузер Playwright
playwright install chromium

# 3. Настроить переменные окружения
cp .env.example .env
# Открыть .env и вписать свой OPENROUTER_API_KEY

# 4. Запустить
python main.py
```

### Ollama (локальная LLM, опционально)

```powershell
# Установить: https://ollama.com
# Скачать vision-модель по объёму RAM:
ollama pull llava:7b        # 4.7 ГБ — работает при 8+ ГБ свободной RAM
ollama pull moondream       # 2 ГБ   — более лёгкая альтернатива
# llama3.2-vision требует 31 ГБ — не рекомендуется без 40+ ГБ
```

Для WSL2 укажите IP хоста в `.env`:
```
OLLAMA_BASE_URL=http://172.29.192.1:11434
```

### OpenRouter (облачная LLM, опционально)

1. Зарегистрироваться на [openrouter.ai](https://openrouter.ai)
2. Создать бесплатный API-ключ
3. Добавить в `.env`: `OPENROUTER_API_KEY=sk-or-v1-...`

Бесплатные vision-модели (проверено март 2026):
- `mistralai/mistral-small-3.1-24b-instruct:free` (рекомендуется)
- `google/gemma-3-12b-it:free`
- `nvidia/nemotron-nano-12b-v2-vl:free`

## Как добавить новый плагин

Создайте новый файл в `plugins/`, например `plugins/my_custom.py`:

```python
from plugins.context import PluginContext


class MyCustomPlugin:
    name = "my_custom"
    priority = 350

    def can_handle(self, page) -> bool:
        return "my screen marker" in (page.inner_text("body") or "").lower()

    def execute(self, page) -> bool:
        # выполнить нужное действие
        return True


def create_plugin(ctx: PluginContext):
    # ctx.defaults доступен для пользовательских данных, если нужно
    return MyCustomPlugin()
```

Плагин загрузится автоматически при следующем запуске `python main.py`.

## Результаты

Каждый запуск сохраняет в `results/<ключ-воронки>/`:
- `01_question.png`, `02_email.png`, ... — скриншот каждого шага
- `log.txt` — лог с типами экранов и URL

Скриншоты также копируются в `results/_classified/<тип_экрана>/` для анализа.

## Тесты

```bash
python -m unittest discover tests/
```

## Поддерживаемые типы чекбоксов

Стратегия email обрабатывает три паттерна чекбоксов согласия:
1. **Нативный `input[type='checkbox']`** — с фоллбеком через React event dispatch
2. **`[data-testid='checkbox']` div-ы** — кастомные чекбоксы в стиле Coursiv
3. **`cursor-pointer` div-ы рядом с текстом согласия** — JS-based универсальный фоллбек
