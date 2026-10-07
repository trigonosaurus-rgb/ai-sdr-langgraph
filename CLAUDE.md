# AI SDR

Портфолио-проект: веб-приложение, которое исследует компанию и готовит персонализированное холодное письмо с проверкой человеком. План и статус этапов — [ROADMAP.md](ROADMAP.md).

## Структура

- `core/graph.py` — LangGraph: `researcher → strategist → copywriter ⇄ reviewer`, ранний выход после research. `core/runner.py` запускает граф, нумерует события и решает итог (`ready` / `needs_attention` / `failed`).
- `core/schemas.py` — бриф, structured output (Pydantic), результат запуска. `core/config.py` — модели и reasoning effort по этапам, лимит переписываний (`OPENAI_MODEL_NAME`, `SDR_MAX_REWRITES`).
- `core/llm.py` — structured output через LangChain + usage из метаданных API; `core/search.py` — Tavily; `core/context.py` — зависимости запуска и журнал всех платных вызовов, включая неудачные.
- `core/events.py` — события, зеркало `frontend/src/run.ts`; `tests/test_events.py` проверяет совпадение типов.
- `agents/` — узлы графа (фабрики `make_*(ctx)`). `prompts/*.md` — промпты с `version` во front matter.
- `core/cli.py` — ручной запуск до появления API.
- `tests/` — pytest на фейковых LLM и поиске (`tests/fakes.py`), без сети.
- `frontend/` — React 19 + TypeScript + Vite. **Не подключён к графу**: генерация отключена, данные в Examples вымышленные (Northstar). Детали — [frontend/README.md](frontend/README.md), требования к будущему API — [frontend/INTEGRATION.md](frontend/INTEGRATION.md).
- `frontend/src/run.ts` — контракт событий и reducer для будущего streaming. Меняя событие, менять и `core/events.py`.

## Команды

Окружение: Windows, PowerShell. В PowerShell использовать `npm.cmd`/`npx.cmd`.

```powershell
# Frontend (из frontend/)
npm.cmd run dev            # http://127.0.0.1:5173 — перед запуском проверить, не занят ли порт
npm.cmd test               # Vitest
npm.cmd run test:browser   # Playwright, нужен установленный Microsoft Edge
npm.cmd run build          # tsc + vite build
npm.cmd run format:check

# Python (из корня)
.venv\Scripts\python.exe -m pytest                  # без сети
.venv\Scripts\python.exe -m core.cli --help         # запуск — ПЛАТНЫЕ вызовы OpenAI и Tavily
```

## Зависимости Python

Прямые зависимости — в `requirements.in` (runtime) и `requirements-dev.in` (тесты, pip-tools); точные версии — в скомпилированных `requirements.txt` / `requirements-dev.txt`. Lock-файлы руками не править.

```powershell
# Добавить или поднять пакет: правка .in, затем пересборка обоих lock-файлов по порядку
.venv\Scripts\pip-compile.exe --strip-extras requirements.in
.venv\Scripts\pip-compile.exe --strip-extras requirements-dev.in
# Обновить всё до последних версий: те же команды с --upgrade (или --upgrade-package <имя>)
.venv\Scripts\pip-sync.exe requirements-dev.txt   # привести .venv точно к lock-файлу
```

После обновления `langchain-*`, `openai`, `langgraph` или `tavily-python` — pytest и, с согласия пользователя, один платный запуск CLI: structured output, usage и кредиты Tavily на новых версиях не гарантированы. Пакеты с платформенными extras (например `uvicorn[standard]`) не добавлять: lock собирается на Windows, а образ будет Linux.

## Правила

- Ключи лежат в корневом `.env`. Не выводить его содержимое, не копировать ключи во frontend; провайдерские ключи остаются только на сервере.
- Не запускать реальные агенты (CLI, граф, вызовы OpenAI/Tavily) без явного согласия пользователя — это стоит денег.
- Не показывать выдуманные цифры как реальные: неизвестные токены/стоимость — прочерк, не ноль. Вымышленные данные явно помечать.
- Визуальные изменения фронтенда проверять в браузере (Playwright MCP) на десктопе и мобильной ширине, в светлой и тёмной теме.
- Коммитить после каждого законченного шага с понятным сообщением; пушить и создавать PR — по согласованию. Резервные копии — через git, не zip-архивы.
- Общение с пользователем — на русском. Код, комментарии и коммиты — на английском.
