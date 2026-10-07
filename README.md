# AI SDR

Researches a company and drafts a personalized cold email for a human to review. You give the company, its website, your offer, the recipient's role, the language and the tone; you get facts with source links and verbatim quotes, an approach that separates facts from hypotheses, and a reviewed draft.

Work in progress. The plan and stage status are in [ROADMAP.md](ROADMAP.md).

## How it works

A LangGraph workflow: `researcher → strategist → copywriter ⇄ reviewer`.

1. **Research** runs three Tavily searches (the official site, the open web, recent news) and extracts facts with structured output. A fact is kept only if its quote is found verbatim in the cited page. The run stops honestly when the results describe a different company than the given website, or when there is too little to write a specific email.
2. **Strategy** picks one observation grounded in the facts, links it to the offer, lists assumptions as hypotheses and judges how well the offer fits.
3. **Writing** drafts the subject and body in the chosen language and tone. A rewrite sees the previous draft and the review issues.
4. **Review** checks language, tone, grounding, spamminess and placeholders. The number of rewrites is configurable.

Every run ends as `ready`, `needs_attention` (a draft exists but did not pass review, or the offer looks like a poor fit) or `failed`. A model or parsing error never becomes the result and never counts as a passed review. Prompts live in versioned files under `prompts/`, and each result records the prompt versions and the token usage reported by the API for each call.

The React frontend in [`frontend/`](frontend/README.md) talks to a FastAPI server (`server/`): it starts a run, follows its events over SSE as the draft is written, can cancel it and restores it after a reload. Runs, events and paid calls are stored in SQLite. Its Examples still use fictional data.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`requirements.txt` and `requirements-dev.txt` are pinned lock files compiled with pip-tools from `requirements.in` and `requirements-dev.in`.

Create `.env` in the repository root:

```env
OPENAI_API_KEY=...
TAVILY_API_KEY=...
OPENAI_MODEL_NAME=gpt-5.4-mini   # optional
SDR_MAX_REWRITES=2               # optional
SDR_DB_PATH=data/sdr.sqlite3     # optional, API storage
SDR_RUNS_PER_DAY=3               # optional, per client address, rolling 24 hours
SDR_RUNS_PER_MONTH=10            # optional, per client address, rolling 30 days
SDR_MONTHLY_MODEL_USD=5          # optional, model spending per calendar month (UTC)
SDR_MONTHLY_SEARCH_CREDITS=750   # optional, Tavily credits per calendar month (UTC)
SDR_MAX_CONCURRENT_RUNS=4        # optional, for the whole server
SDR_CLIENT_SALT=...              # optional, salt for hashed client addresses
SDR_DEVELOPER_KEY=...            # optional, open /#developer=<key> once for runs without limits
```

## Run

In the browser (API on :8000, Vite on :5173). Generate makes paid OpenAI and Tavily calls:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev:all
```

From the terminal, also paid:

```powershell
.venv\Scripts\python.exe -m core.cli --company "Acme" --website acme.com `
  --offer "Contract data engineers for analytics teams" --recipient "VP of Engineering" `
  --language English --tone Direct
```

Progress goes to stderr, the draft to stdout, and the full result with facts, attempts, prompt versions and usage to `runs/<run_id>.json`.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest     # fake LLM and search, no network
```
