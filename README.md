# Mini-MAPPy

AI-assisted MBSE tooling. Give it a plain-English system description; it drafts
requirements that conform to the INCOSE writing rules and a SysML block
definition diagram, traces one to the other, and meters what the generation
cost in tokens, seconds, and dollars.

Four things happen to every generated artifact:

1. **Lexical validation** against the INCOSE writing rules, with failures
   driving a targeted rewrite rather than a rejection.
2. **Semantic review** by a second model, scoring what a regex cannot see —
   whether a requirement is singular, verifiable, and implementation-free.
3. **Traceability** linking requirements to the design elements that satisfy
   them, which makes coverage gaps computable.
4. **Metering** of tokens, latency, conformance, and cost on every call.

Runs against a local model through [Ollama](https://ollama.com) by default, or
against the hosted Anthropic API — the same pipeline, so the tradeoff between
them is measured rather than assumed.

---

## The part that isn't just an LLM call

An LLM asked for INCOSE-conformant requirements will produce plausible prose
that quietly breaks the rules. This project treats that as the engineering
problem rather than the finished product:

1. **The rulebook is executable.** `rules.py` implements eight checks — minimum
   length, presence of "shall", vague terms, unachievable absolutes, bare
   pronouns, escape clauses, open-ended clauses, superfluous phrases — plus a
   batch-level near-duplicate detector that no per-requirement check could catch.

2. **Violations drive a targeted retry.** A failing requirement is re-prompted
   with *the specific rules it broke*, not a generic "try again", bounded at
   three attempts so worst-case cost stays bounded.

3. **The loop's value is measured, not asserted.** On the benchmark suite,
   locally generated requirements pass all rules first try **50%** of the time
   and are valid after self-correction **93%** of the time. That 43-point lift
   is what the validation layer buys.

Diagrams get the same treatment with different rules: validation there is
referential integrity (every connector resolves to a real block, exactly one
root, no self-loops, kinds from the allowed set), and repair re-prompts the
whole graph rather than one node.

---

## Architecture

```
┌──────────────┐   HTTP/JSON   ┌───────────────┐   ┌─────────────────┐
│  React (SPA) │ ────────────▶ │  FastAPI       │──▶│ Ollama (local)  │
│  :5173       │ ◀──────────── │  :8000         │   └─────────────────┘
└──────────────┘               │                │   ┌─────────────────┐
                               │  llm.py routes │──▶│ Anthropic API   │
                               │  by model id   │   └─────────────────┘
                               └───────┬────────┘
                                       ▼
                              data/state.json
                   (model elements, diagram, activity + eval logs)
```

`llm.py` dispatches on the model id — `claude-*` goes to the Anthropic SDK,
anything else to Ollama — and both return the same result shape, so the rule
engine, repair loop, and metrics are provider-agnostic.

---

## Quickstart

Requires Python 3.12+, Node 18+, and [Ollama](https://ollama.com).

```bash
ollama pull llama3.1:8b     # ~4.9 GB, one time
./scripts/dev.sh
```

That's it. The script creates the virtualenv and installs both dependency sets
on first run, frees the ports if something is already on them, starts the API
and the dev server, **waits until each actually answers**, and opens the app.

- App — <http://localhost:5173>
- Full-size diagram — <http://localhost:5173/diagram-view>
- API docs — <http://localhost:8000/docs>

```bash
./scripts/dev.sh --no-open   # same, without launching a browser
./scripts/stop.sh            # stop both servers
tail -f /tmp/mappy-backend.log
```

**Optional — hosted models.** Copy `backend/.env.example` to `backend/.env` and
add an Anthropic API key. Claude models then appear in the model picker
alongside the local ones. Without a key the app runs fully local and offline.

<details>
<summary>Running the servers by hand</summary>

```bash
# terminal 1
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# terminal 2 — only after the API answers on :8000
cd frontend
npm install
npm run dev
```

The ordering matters. The frontend fetches its data once when the page mounts,
so if the API isn't answering yet you get a "Load failed" banner that does not
retry on its own — reload the page once the backend is up. `scripts/dev.sh`
exists to make that race impossible.

</details>

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR: [Errno 48] Address already in use` | A server from a previous session is still running (`nohup`/`&` survives closing the terminal) | `./scripts/stop.sh`, or just re-run `./scripts/dev.sh` — it clears the ports itself |
| "Load failed" banner, "No models available" | Page mounted before the API was answering | Reload the page. Use `./scripts/dev.sh` to avoid it |
| Generation fails against a local model | Ollama not running, or the model was never pulled | `ollama serve` and `ollama pull llama3.1:8b` |
| Claude models missing from the picker | No API key | Add `ANTHROPIC_API_KEY` to `backend/.env` and restart |

---

## Traceability

Requirements and design elements are only useful together. The app links them
with SysML relationships — `satisfy`, `refine`, `verify` — and computes the
two findings that matter in a design review:

- **Uncovered requirements** — agreed, written down, and allocated to nothing
  that builds them. Only `satisfy` counts here; refining or verifying a
  requirement does not mean anything fulfils it.
- **Orphan blocks** — design elements that satisfy no stated requirement.
  Either a requirement is missing, or the element is unjustified scope.

The model proposes the matrix and a human confirms it. Suggestions are
validated against the real id sets before they are shown, so a hallucinated
link is dropped rather than surfaced, and nothing is written to the model until
the engineer accepts it. Asked to link requirements about a launch vehicle to a
diagram of an unrelated system, it correctly proposed nothing.

---

## Evaluation

Every generation records tokens in/out, LLM call count (including each repair
attempt), wall clock, items produced, first-pass conformance, and final
conformance. Cost is derived at read time from stored token counts, so
correcting a published rate reprices history rather than leaving stale figures
baked into old records.

A fixed golden set of six prompts re-runs on demand, so a prompt or model change
is compared on identical inputs:

```bash
curl -X POST localhost:8000/evaluations/run-suite \
  -H 'Content-Type: application/json' -d '{"model":"llama3.1:8b"}'
```

Same six prompts, both providers:

| | `llama3.1:8b` (local) | `claude-haiku-4-5` (hosted) |
|---|---|---|
| Requirements produced | 11 | 32 |
| Diagram blocks | 22 | 30 |
| First-pass rate | 50% | 63% |
| Final success rate | 93% | 97% |
| Tokens | 17,487 | 38,418 |
| Wall clock | 290s | 136s |
| Cost | free | $0.0910 |

The local model is slower and less thorough, but self-correction closes most of
the conformance gap. For controlled documents the deciding factor is usually
data residency rather than the sub-cent cost difference.

### Semantic review: what the rule engine cannot see

The rule engine is lexical. It verifies a requirement is *written* well; it
cannot tell you whether the requirement bundles three needs into one sentence,
or states something no test could falsify. A second model scores the same
requirements on criteria a regex cannot reach — singular, verifiable,
implementation-free, unambiguous, necessary — and the two signals are
cross-tabulated.

On the current model elements, **2 of 5 requirements passed every lexical rule
but were flagged by semantic review**, both for bundling multiple needs into a
single requirement. That number is the honest bound on what lexical validation
buys you, and it is measured rather than asserted.

### Prompt caching: measured, and it does not help here

The system instructions are byte-identical on every call, so they are marked
cacheable. Measured on 2026-09-13, **this currently no-ops**: a prefix shorter
than the model's minimum cacheable length is silently not cached, and these
instructions are ~700-930 tokens. Probing with a padded prompt confirmed the
implementation is correct — Sonnet 5 at ~4.5k tokens wrote the cache on the
first call and read it back on the second, dropping billed input from 932 to 14
tokens. Haiku 4.5 did not cache even at ~2.5k, so its minimum is higher.

Padding the prompt to cross that threshold would be a net loss: you would pay
for thousands of filler input tokens to earn a discount on those same tokens.
The plumbing stays because it starts paying the moment the instructions
genuinely grow — few-shot examples, or the INCOSE rule text inline.

### What the evals caught

Their first run exposed a silent failure that manual testing had missed: the
requirements parser assumed a JSON array, but the model sometimes returns a
single bare requirement object, and the whole generation was being discarded.
Two of three requirements prompts were producing nothing. The fix was four
lines; the same suite verified it.

---

## Layout

```
backend/app/
  llm.py              provider router + shared result type
  ollama_client.py    local provider
  anthropic_client.py hosted provider
  prompts.py          system instructions + repair prompts
  rules.py            INCOSE rule engine (8 checks + duplicate detection)
  diagram_rules.py    SysML structural/referential validation
  traceability.py     satisfy/refine/verify links + coverage analysis
  judge.py            semantic review scoring, cross-tabbed with the rules
  evaluation.py       metrics, cost model, aggregation
  eval_suite.py       golden prompt set
  storage.py          JSON persistence behind a lock
  routes/             requirements, diagram, traces, evaluations, models,
                      elements, log
frontend/src/
  components/         GenerationForm, RequirementsList, BlockDiagram,
                      EvaluationsPanel, ModelElementsPanel, ActivityLog
  DiagramPage.jsx     standalone full-size diagram route
scripts/
  dev.sh              setup + start both servers, wait until each answers
  stop.sh             stop both servers
```

```bash
cd backend && pytest app/tests -q    # 23 tests: rules, traceability, judge
cd frontend && npx oxlint src/ && npx vite build
```

---

## Limitations

Stated plainly, because they bound what this is useful for:

- **Nothing here establishes that a requirement is _correct_.** The rule engine
  checks how it is written. The semantic reviewer goes further — it catches
  requirements that bundle several needs or cannot be objectively tested — but
  the reviewer is itself a language model, not ground truth: it is
  non-deterministic, it can be wrong, and it has no access to the stakeholder
  need the requirement is supposed to serve. Treat its scores as a prioritised
  reading list for a human, not a gate. A human promotes each requirement into
  the model; the tool removes conformance drudgery, not the engineer.
- **Trace links are proposed, not derived.** The model infers them from wording
  overlap between a requirement and a block description. Hallucinated ids are
  dropped before display, but a plausible-looking wrong link will be shown —
  which is why nothing persists until a human accepts it.
- **The 40-word minimum is a proxy, not a literal INCOSE rule** — a cheap stand-in
  for completeness. The vague-terms, absolutes, and escape-clause checks map far
  more directly to the guidance. All the term lists are plain data at the top of
  `rules.py` so a systems engineer can tune them.
- **No SysML interchange.** Output is application JSON, not XMI, so it does not
  round-trip into Cameo or Rhapsody.
- **Duplicate detection is string similarity**, so it catches restatements, not
  two differently-worded requirements that mean the same thing.
- **JSON file storage** — single user, no concurrent writers. Isolated behind
  `storage.py` so the swap to a real database touches one module.
