# Mini-MAPPy

AI-assisted MBSE tooling. Give it a plain-English system description; it drafts
requirements that conform to the INCOSE writing rules and a SysML block
definition diagram, validates both programmatically, and meters what the
generation cost in tokens, seconds, and dollars.

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

Requires Python 3.12+, Node 18+, and Ollama.

```bash
# model (~4.9 GB)
ollama pull llama3.1:8b

# backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The standalone diagram view is at `/diagram-view`.

**Optional — hosted models.** Copy `backend/.env.example` to `backend/.env` and
add an Anthropic API key. Claude models then appear in the model picker
alongside the local ones. Without a key the app runs fully local and offline.

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
  evaluation.py       metrics, cost model, aggregation
  eval_suite.py       golden prompt set
  storage.py          JSON persistence behind a lock
  routes/             requirements, diagram, evaluations, models, elements, log
frontend/src/
  components/         GenerationForm, RequirementsList, BlockDiagram,
                      EvaluationsPanel, ModelElementsPanel, ActivityLog
  DiagramPage.jsx     standalone full-size diagram route
```

```bash
cd backend && pytest app/tests -q    # 12 tests over the rule engine
cd frontend && npx oxlint src/ && npx vite build
```

---

## Limitations

Stated plainly, because they bound what this is useful for:

- **Validation is lexical, not semantic.** The engine verifies a requirement is
  *well written*, not that it is correct, necessary, or traceable to a real
  stakeholder need. A human promotes each requirement into the model; the tool
  removes conformance drudgery, not the engineer.
- **The 40-word minimum is a proxy, not a literal INCOSE rule** — a cheap stand-in
  for completeness. The vague-terms, absolutes, and escape-clause checks map far
  more directly to the guidance. All the term lists are plain data at the top of
  `rules.py` so a systems engineer can tune them.
- **No traceability model.** Requirements and diagram blocks are separate
  collections with no `satisfy` / `derive` links between them.
- **No SysML interchange.** Output is application JSON, not XMI, so it does not
  round-trip into Cameo or Rhapsody.
- **Duplicate detection is string similarity**, so it catches restatements, not
  two differently-worded requirements that mean the same thing.
- **JSON file storage** — single user, no concurrent writers. Isolated behind
  `storage.py` so the swap to a real database touches one module.
