# Reproducing the demo

| | |
|---|---|
| Hardware | MacBook Pro (`MacBookPro18,3`), Apple silicon, arm64 |
| Memory | 16 GB |
| OS | macOS 15.5 (build 24F74) |
| Python | 3.14.7 |
| Node | v22.13.1, npm 10.9.2 |
| Ollama | 0.33.3 |
| SQLite | 3.43.2 |
| Measured | 12 to 13 September 2026 |

Memory is the constraint worth naming. 16 GB is why the local model is
`llama3.1:8b` and not something larger, and it bounds the local side of every
comparison in the README.

Ollama model digests, so you can confirm you are running the same weights:

```
llama3.1:8b              46e0c10c039e    4.9 GB
nomic-embed-text:latest  0a109f422b47    274 MB
```

```bash
ollama list    # compare the ID column against the digests above
```

Python and Node dependencies are pinned in `backend/requirements.txt` and
`frontend/package-lock.json`. `./scripts/dev.sh` installs both from those files
on first run, so a fresh clone resolves the same versions.

---

## Start from a clean slate

**This step is not optional if you want the suite table to match.** The
evaluation log is cumulative and the suite summary filters the whole stored log
by `source = "suite"`, so running the suite twice without clearing averages both
runs together and the second table will not match the first.

```bash
./scripts/reset.sh --everything    # drops the eval history too
./scripts/dev.sh
```

`reset.sh` on its own keeps the evaluation history, which is what you want
between demo takes and not what you want here.

---

## The golden suite table

Reproduces the six-prompt table under **Evaluation**, and the 50% / 93% figures
quoted under **Why this is more than one LLM call**.

Six fixed prompts, three for requirements and three for diagrams, defined in
`backend/app/eval_suite.py`. They are hardcoded so a prompt change or a model
change is compared on identical inputs.

```bash
curl -X POST localhost:8000/evaluations/run-suite \
  -H 'Content-Type: application/json' -d '{"model":"llama3.1:8b"}' | jq '.suite_summary'
```

Expect this to take several minutes on a local 8B model. It runs six real
generations sequentially, it is not mocked.

Read the figures off `suite_summary`:

| README row | Field |
|---|---|
| First-pass rate | `avg_first_pass_rate` |
| Final success rate | `avg_success_rate` |
| Tokens | `total_tokens` |
| Wall clock | `total_duration_ms` |
| Cost | `actual_spend_usd` |

The requirement and block counts are per task, so they come from the log rather
than the summary:

```bash
curl -s localhost:8000/evaluations | jq '
  [.records[] | select(.source=="suite")]
  | {requirements: [.[] | select(.task=="requirements") | .items] | add,
     blocks:       [.[] | select(.task=="diagram")      | .items] | add}'
```

For the hosted column, clear and repeat with `{"model":"claude-haiku-4-5"}`.
That requires `ANTHROPIC_API_KEY` in `backend/.env` and it spends real money,
about $0.09 for the six prompts at the rates below.

The Evaluations tab in the UI runs the same thing if you would rather click it.

---

## The head-to-head table

Reproduces the two-row table under **Shortcomings in the source material**.

One prompt, "a satellite ground station that tracks a single LEO spacecraft",
run through each model back to back so the rows are comparable by construction.
This is the fix for the README's own criticism of the provider table, which
compares runs that were never controlled against each other.

```bash
curl -X POST localhost:8000/evaluations/head-to-head \
  -H 'Content-Type: application/json' \
  -d '{"models":["claude-haiku-4-5","llama3.1:8b"]}' | jq '.rows'
```

Each row carries `items`, `first_pass_rate`, `success_rate`, `duration_ms`,
`actual_cost_usd`, and `rules_broken`, which map one to one onto the table
columns. `rules_broken` is the interesting field and is not in the README
table: it names which `MM-*` checks each model actually failed.

---

## The rule engine

These are deterministic. They are pure functions over text with no model in the
loop, so they either reproduce exactly or something is wrong.

```bash
cd backend && source venv/bin/activate
pytest app/tests -q          # 67 tests
```

Covers the rule engine, retrieval chunking and scoring, malformed-output
recovery, traceability coverage, and the semantic reviewer's scoring.

The ten checks and the INCOSE characteristic each serves are in `RULE_CATALOG`
at the top of `backend/app/rules.py`. The README table is generated from
nothing, it is transcribed from that dict, so check it there if you want the
authoritative list.

---

## Cost figures

Costs are not measured, they are derived at read time from stored token counts
against the rates in `REFERENCE_RATES` in `backend/app/evaluation.py`:

| Model | Input, USD per 1M | Output, USD per 1M |
|---|---|---|
| claude-haiku-4-5 | 1.00 | 5.00 |
| claude-sonnet-5 | 2.00 | 10.00 |
| claude-opus-5 | 5.00 | 25.00 |

Verified 2026-06-24 against Anthropic's published pricing. Re-check
<https://www.anthropic.com/pricing> before quoting them, since a stale rate
table silently reprices every number in this file.

Deriving cost at read time rather than storing it is deliberate: correcting a
rate reprices history instead of leaving stale figures baked into old records.
Local generations are free and record a cost of zero.

---

## What will not reproduce exactly

Be honest about this when comparing. Three different kinds of number are quoted
in the README and they have three different reliabilities.

**Deterministic, should match exactly.** The 67 tests, the rule catalog, the
INCOSE characteristic mapping, and the cost arithmetic for a given token count.

**Stable in shape, not in digits.** The suite and head-to-head rates, token
counts, and latencies. Both providers sample at a non-zero temperature, so
first-pass rate and output volume move between runs. The pattern the README
draws on is what survives re-running: the repair loop closes most of the gap
between first-pass and final conformance, and the local model produces less
output than the hosted one. A single run's exact percentage does not survive,
and the README quotes it as a measurement of one run rather than a benchmark.

Latency depends on your hardware and, for the hosted model, on network and
server load. The local figures assume the model is already resident. A cold
first call after `ollama pull` pays the load cost and will look much worse.

**One observed run, reported as such.** The claim that generating a diagram
from kept requirements took proposed trace links from 5 to 10 and dropped
orphan blocks from 7 to 1 is a single before-and-after on one ground station
example, not an averaged result. The procedure reproduces, generate a diagram
with no requirements kept, then keep a set and regenerate, and the direction
should hold. The specific integers will not.

Nothing in this file establishes that a generated requirement is *correct*.
It establishes that the pipeline behaves the way the README says it does. The
[Limitations](README.md#limitations) section is the honest boundary.
