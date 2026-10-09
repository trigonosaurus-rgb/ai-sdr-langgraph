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

## Quality and model choice

Measured on 28 briefs in [`evals/`](evals/README.md): well-known and small companies, ambiguous names, fictional companies, a website that belongs to someone else, an offer that does not fit, English and Russian. 8 briefs are held out from tuning. Search results are recorded once and replayed, so every configuration sees the same pages. Each configuration ran every development brief twice.

| Configuration (prompts v2) | Outcome as expected | Successful runs | Model cost per success | Median time |
| --- | --- | --- | --- | --- |
| `gpt-5.4-mini`, prompts v1 (baseline) | 34/40 | 24/40 | $0.021 | 16 s |
| **`gpt-5.4-mini`** | **40/40** | **37/40** | $0.013 | **14 s** |
| `gpt-6-luna` | 40/40 | 32/40 | $0.0015 | 19 s |
| `gpt-6.1-sol` | 40/40 | 35/40 | $0.023 | 30 s |
| luna research, sol strategy, mini writing and review | 40/40 | 35/40 | $0.010 | 20 s |
| **`gpt-5.4-mini`, held-out briefs** | **16/16** | **13/16** | $0.015 | 16 s |

- **Outcome as expected**: a draft where one is warranted, a refusal for a wrong website or too little information, a poor-fit warning for an unrelated offer. Checked automatically.
- **Successful**: the outcome is right and, for a draft, it is fully grounded and scores at least 5 of 6 on grounding, relevance and naturalness. Drafts were graded by Claude (Anthropic): a different vendor from the models under test, but still an LLM, and it knew which configuration it was grading.
- **Blind human check**: the author graded 26 drafts with the configuration hidden. On grounding the grades matched Claude's 25 times out of 26; Claude was more generous on relevance (+0.31 on a 0–2 scale) and naturalness (+0.35), so naturalness scores above are optimistic. The human grades also ranked `gpt-5.4-mini` with prompts v2 first.
- **Cost** is the model only, from list prices. Search adds $0.024 per run (3 Tavily credits at the pay-as-you-go rate), more than the model for every configuration except sol.

The biggest gain came from fixes, not from a bigger model: the quote check had rejected Russian quotes in guillemets, the website check asked an ambiguous question and accepted a competitor's site, and the review blocked drafts over style. `gpt-5.4-mini` stays on every stage: best results, fastest, one model.
