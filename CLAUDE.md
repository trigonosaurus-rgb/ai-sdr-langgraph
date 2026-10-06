# AI SDR

Портфолио-проект: веб-приложение, которое исследует компанию и готовит персонализированное холодное письмо с проверкой человеком. План и статус этапов — [ROADMAP.md](ROADMAP.md).

## Структура

- `core/graph.py` — LangGraph: `researcher → strategist → copywriter ⇄ spam_checker`. Состояние — `core/state.py`, LLM — `core/llm.py` (OpenAI через LangChain, модель из `OPENAI_MODEL_NAME`, по умолчанию `gpt-5.4-mini`).
- `agents/` — узлы графа. Поиск — Tavily.
- `app.py` — Streamlit, временный способ реального запуска до появления API.
- `frontend/` — React 19 + TypeScript + Vite. **Не подключён к графу**: генерация отключена, данные в Examples вымышленные (Northstar). Детали — [frontend/README.md](frontend/README.md), требования к будущему API — [frontend/INTEGRATION.md](frontend/INTEGRATION.md).
- `frontend/src/run.ts` — прототип контракта событий и reducer для будущего streaming, не финальная схема API.

Бриф во фронтенде (`company, website, offer, recipient, language, tone`) шире, чем вход графа (`company_name, company_url`): offer/recipient/language/tone бэкенд пока не принимает.

## Команды

Окружение: Windows, PowerShell. В PowerShell использовать `npm.cmd`/`npx.cmd`.

```powershell
# Frontend (из frontend/)
npm.cmd run dev            # http://127.0.0.1:5173 — перед запуском проверить, не занят ли порт
npm.cmd test               # Vitest
npm.cmd run test:browser   # Playwright, нужен установленный Microsoft Edge
npm.cmd run build          # tsc + vite build
npm.cmd run format:check

# Python
.venv\Scripts\python.exe -m streamlit run app.py   # ПЛАТНЫЕ вызовы OpenAI и Tavily
```

## Правила

- Ключи лежат в корневом `.env`. Не выводить его содержимое, не копировать ключи во frontend; провайдерские ключи остаются только на сервере.
- Не запускать реальные агенты (Streamlit, граф, вызовы OpenAI/Tavily) без явного согласия пользователя — это стоит денег.
- Не показывать выдуманные цифры как реальные: неизвестные токены/стоимость — прочерк, не ноль. Вымышленные данные явно помечать.
- Визуальные изменения фронтенда проверять в браузере (Playwright MCP) на десктопе и мобильной ширине, в светлой и тёмной теме.
- Коммитить после каждого законченного шага с понятным сообщением; пушить и создавать PR — по согласованию. Резервные копии — через git, не zip-архивы.
- Общение с пользователем — на русском. Код, комментарии и коммиты — на английском.
