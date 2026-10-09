# Evaluation

Measures the graph on a fixed set of briefs so that models, reasoning effort and prompts are compared on the same data.

- `cases.toml` — briefs with the outcomes a careful human would accept (`draft`, `poor_fit`, `insufficient_data`, `website_mismatch`). Expectations are set from the recorded sources, never from model outputs. Cases marked `holdout` stay out of tuning and run only for the final check.
- `snapshots/` — the Tavily responses for every case, recorded once. Every configuration replays the same pages, so differences come from the models and prompts, not from the live web. Live search is checked separately.
- `results/<name>/<case>.<repeat>.json` — the full run result, the automatic checks and the models used.

## Commands

```powershell
.venv\Scripts\python.exe -m evals.snapshot                 # PAID: ~3 Tavily credits per new case
.venv\Scripts\python.exe -m evals.run --config mini        # PAID: OpenAI calls, dev split
.venv\Scripts\python.exe -m evals.run --config mini --split holdout --name mini-holdout
.venv\Scripts\python.exe -m evals.report                   # table over all result folders
```

`evals.run` skips results that already exist, so an interrupted run resumes.

## Automatic checks

Objective but shallow: the outcome matches the expectation; the draft is in the requested language; body 50–120 words and subject under 8; no placeholders; every number in the draft appears in a fact or in the brief. A run that passes still needs grading.

## Grading scale

Each draft gets 0–2 on three criteria:

| Criterion   | 2                                                                                     | 1                                                            | 0                                                          |
| ----------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| Grounding   | Every statement about the company is in the facts, and the facts are in the sources   | A rounding or a slight stretch that does not mislead         | A distorted or invented fact, or a hypothesis stated as fact |
| Relevance   | The observation matters to this recipient and the link to the offer is logical        | Generic observation or a stretched link                      | Irrelevant or forced                                       |
| Naturalness | Reads like one person writing to another, in the requested language and tone          | Usable after light editing                                   | Template-like, salesy or awkward                           |

Refusals and poor-fit warnings are judged by the outcome check against the expectation.

Who grades is stated next to every number: Claude (a different vendor from the models under test, but still an LLM) grades all drafts with a written reason; a human grades a blind sample of about a quarter, and agreement between the two is reported. Grades by an OpenAI model are not used, since the models under test are OpenAI's.
