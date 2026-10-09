# AI SDR

Портфолио-проект: веб-приложение, которое исследует компанию и готовит персонализированное холодное письмо с проверкой человеком. План и статус этапов — [ROADMAP.md](ROADMAP.md).

## Структура

- `core/graph.py` — LangGraph: `researcher → strategist → copywriter ⇄ reviewer`, ранний выход после research. `core/runner.py` запускает граф, нумерует события и решает итог (`ready` / `needs_attention` / `failed`).
- `core/schemas.py` — бриф, structured output (Pydantic), результат запуска. `core/config.py` — модели и reasoning effort по этапам, лимит переписываний (`OPENAI_MODEL_NAME`, `SDR_MAX_REWRITES`).
- `core/llm.py` — structured output через LangChain + usage из метаданных API; `core/search.py` — Tavily; `core/context.py` — зависимости запуска и журнал всех платных вызовов, включая неудачные; перед каждым вызовом — отмена и `before_call` (суточный бюджет), после — `on_record`.
- `core/pricing.py` — таблица тарифов с датой-версией. Стоимость вызова фиксируется при записи и не пересчитывается; при смене цен — новая версия таблицы, старые записи не трогать.
- `core/events.py` — события, зеркало `frontend/src/run.ts`; `tests/test_events.py` проверяет совпадение типов.
- `agents/` — узлы графа (фабрики `make_*(ctx)`). `prompts/*.md` — промпты с `version` во front matter.
- `core/cli.py` — ручной запуск из терминала.
- `evals/` — оценка качества: случаи `cases.toml`, снимки поиска `snapshots/`, прогон с конфигурацией моделей (`configs.py`), автопроверки, отчёт. Описание и шкала — [evals/README.md](evals/README.md).
- `server/app.py` — FastAPI: `POST /api/runs`, SSE `GET /api/runs/{id}/events` (повтор по `after` / `Last-Event-ID`), `POST /api/runs/{id}/cancel`, снимок `GET /api/runs/{id}`. `GET /api/runs/{id}/usage`, `GET /api/usage?period=24h|30d`, `GET /api/status` (пауза сервиса, режим разработчика и квота посетителя). Разработчик без лимитов — по `SDR_DEVELOPER_KEY` в заголовке `X-Developer-Key`. `server/runs.py` — граф в пуле потоков, отмена, пробуждение SSE, квота посетителя (`SDR_RUNS_PER_DAY` / `SDR_RUNS_PER_MONTH`) и месячный бюджет сервиса (`SDR_MONTHLY_MODEL_USD`, `SDR_MONTHLY_SEARCH_CREDITS`); `server/store.py` — SQLite (`runs`, `events`, `llm_calls`, `search_calls`; вызовы пишутся сразу по завершении), агрегаты usage, миграции через `PRAGMA user_version`, база по умолчанию `data/sdr.sqlite3` (`SDR_DB_PATH`).
- `tests/` — pytest на фейковых LLM и поиске (`tests/fakes.py`), без сети; `tests/test_api.py` — API на фейковом графе.
- `frontend/` — React 19 + TypeScript + Vite, подключён к API через прокси `/api`. Данные в Examples пока вымышленные (Northstar). Детали — [frontend/README.md](frontend/README.md), контракт API — [frontend/INTEGRATION.md](frontend/INTEGRATION.md).
- `frontend/src/run.ts` — контракт событий и reducer. Меняя событие, менять и `core/events.py`. `src/api.ts` — запросы, валидация брифа и событий, SSE; `src/useRun.ts` — запуск, отмена, восстановление после перезагрузки.
- `tests/fake_server.py` — настоящий API на сценарном фейковом графе для e2e (компания со словом `slow` — медленный запуск, `broken` — сбой).

## Команды

Окружение: Windows, PowerShell. В PowerShell использовать `npm.cmd`/`npx.cmd`.

```powershell
# Frontend (из frontend/)
npm.cmd run dev:all        # API :8000 + Vite :5173; Generate — ПЛАТНЫЕ вызовы. Перед запуском проверить порты
npm.cmd run dev            # только Vite :5173 (без API сервис показан недоступным)
npm.cmd test               # Vitest
npm.cmd run test:browser   # Playwright + Edge; сам поднимает фейковый API :8765 и Vite :5174, без платных вызовов
npm.cmd run build          # tsc + vite build
npm.cmd run format:check

# Python (из корня)
.venv\Scripts\python.exe -m pytest                  # без сети
.venv\Scripts\python.exe -m core.cli --help         # запуск — ПЛАТНЫЕ вызовы OpenAI и Tavily
.venv\Scripts\python.exe -m uvicorn server.app:app --port 8000   # API; POST /api/runs — ПЛАТНЫЙ запуск
.venv\Scripts\python.exe -m evals.snapshot   # ПЛАТНО: кредиты Tavily для новых случаев
.venv\Scripts\python.exe -m evals.run --config mini   # ПЛАТНО: OpenAI на снимках поиска
.venv\Scripts\python.exe -m evals.report           # таблица по результатам, без сети
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
