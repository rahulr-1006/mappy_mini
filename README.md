# Mini-MAPPy

AI-assisted MBSE tooling based on MAPPy by Booz Allen Hamilton. Given a plain-text English prompt, it drafts
requirements that conform to the INCOSE writing rules and a SysML block
definition diagram, traces one to the other, and meters what the generation
cost in tokens, seconds, and dollars. This transforms previously manual systems engineering processes into efficient and engineered models.
Hope you enjoy the read and get a chance to test it out on your local machine!

Four things happen to every generated artifact:

1. **Lexical validation** against the INCOSE writing rules, with failures
   driving a targeted rewrite rather than a rejection.
2. **Semantic review** by a second model, scoring what a regex cannot see, such as
   whether a requirement is singular, verifiable, and implementation-free.
3. **Traceability** linking requirements to the design elements that satisfy
   them, which makes coverage gaps computable.
4. **Metering** of tokens, latency, conformance, and cost on every call.

Runs against a local model through [Ollama](https://ollama.com) by default, or
against the hosted Anthropic API using the same pipeline.

---

## Going Beyond a Simple LLM Call

An LLM asked for INCOSE-conformant requirements will produce plausible prose
that quietly breaks the rules. This project treats that as the engineering
problem rather than the finished product:

1. **The rulebook is executable.** `rules.py` implements a series of checks:
- Minimum length check
- Presence of the word "shall"
- Vague terms check
- Unachievable absolutes check
- Bare pronouns check
- Escape clauses check
- Open-ended clauses check
- Superfluous phrases check
- Batch-level near-duplicate detector

2. **Violations drive a targeted retry.** A failing requirement is re-prompted
   with *the specific rules it broke*, not a generic "try again", bounded at
   three attempts so worst-case cost stays bounded. This ensures that key issues
   are addressed step by step without any hallucinations.

3. **The loop's value is measured, not asserted.** On the benchmark suite,
   locally generated requirements pass all rules first try **50%** of the time
   and are valid after self-correction **93%** of the time. That 43-point lift
   is what the validation layer buys.

Diagrams get the same treatment with different rules: validation there is
referential integrity and repair re-prompts the whole graph rather than one node.

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
                               data/mappy.db
                   (model elements, diagram, traces, activity + eval logs)
```

`llm.py` dispatches on the model id and both return the same result shape, so the rule
engine, repair loop, and metrics are provider-agnostic. In this demo's case, 
`claude-*` goes to the Anthropic SDK and anything else goes to Llama.

---

## Quickstart

Requires Python 3.12+, Node 18+, and [Ollama](https://ollama.com).

```bash
ollama pull llama3.1:8b     # ~4.9 GB, one time
./scripts/dev.sh
```

The script creates the virtualenv and installs both dependency sets
on first run, frees the ports if something is already on them, starts the API
and the dev server, **waits until each actually answers**, and opens the app.

- App — <http://localhost:5173>
- Full-size diagram — <http://localhost:5173/diagram-view>
- API docs — <http://localhost:8000/docs>

```bash
./scripts/dev.sh --no-open  
./scripts/stop.sh          
tail -f /tmp/mappy-backend.log
```

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

</details>

---

## Traceability

Requirements and design elements are only useful together. The app links them
with SysML relationships such as `satisfy`, `refine`, `verify`. It then computes the
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

A fixed golden set of six self-created prompts re-runs on demand, so a prompt or model change
is compared on identical inputs. We can change these as needed to ensure proper tailoring:

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
data residency rather than the sub-cent cost difference. The local model is also 
what my machine could computationally do in the scope of the weekend.

### Semantic review: what the rule engine cannot see

The rule engine is lexical. It verifies a requirement is *written* well; it
cannot tell you whether the requirement bundles three needs into one sentence,
or states something no test could falsify. A second model scores the same
requirements on criteria a regex cannot reach and the two signals are
cross-tabulated.

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
  storage.py          SQLite persistence
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
- **Local SQLite database** — single user, no auth. Everything goes through
  `storage.py`, so pointing it at a server database touches one module.
