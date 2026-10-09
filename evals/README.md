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

Blind human grading:

```powershell
.venv\Scripts\python.exe -m evals.blind sample mini-v1 mini-v2 luna-v2 sol-v2 --cases 7 --seed 5   # blind/sample.json + blind/key.json
.venv\Scripts\python.exe -m evals.blind import blind/human-grades.json   # grades/<results>.human.json and agreement with Claude
```

The grader sees `blind/sample.json` (with `blind/sample.ru.json`, Claude's translation for reading only), never the key.

## Automatic checks

Objective but shallow: the outcome matches the expectation; the draft is in the requested language; body 50–120 words and subject under 8; no placeholders; every number in the draft appears in a fact or in the brief. A run that passes still needs grading.

Style tics are counted separately and do not change the draft checks: stock hedges ("my guess is", "I'm assuming", "предполагаю,"), English words in Russian drafts that are not names from the brief or facts, and a Russian company name left undeclined after a preposition ("у Контур"). The report prints them as a second table.

## Grading scale

Each draft gets 0–2 on three criteria:

| Criterion   | 2                                                                                     | 1                                                            | 0                                                          |
| ----------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| Grounding   | Every statement about the company is in the facts (faithful rounding is fine)         | A slight stretch or overgeneralization that does not mislead | A distorted or invented fact, or a hypothesis stated as fact |
| Relevance   | The observation matters to this recipient and the link to the offer is logical        | Generic observation or a stretched link                      | Irrelevant or forced                                       |
| Naturalness | Reads like one person writing to another, in the requested language and tone          | Usable after light editing                                   | Template-like, salesy or awkward                           |

Refusals and poor-fit warnings are judged by the outcome check against the expectation.

A draft is **good** when grounding is 2 and the three scores sum to at least 5: it can be sent after light editing at most. A run is **successful** when its outcome is as expected and, if it is a draft, the draft is good. The report divides the model cost of all runs by the successful ones, so failures count toward the price of a good result.

Grades live in `grades/<results>.<grader>.json` (`claude` or `human`), keyed by `<case>.<repeat>`.

Who grades is stated next to every number: Claude (a different vendor from the models under test, but still an LLM) grades all drafts with a written reason; a human grades a blind sample of about a quarter, and agreement between the two is reported. Grades by an OpenAI model are not used, since the models under test are OpenAI's.
