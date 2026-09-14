# Mini-MAPPy

**DEMO:** https://youtu.be/kb3O7bzeyWg
 
AI-assisted MBSE tooling based on MAPPy by Booz Allen Hamilton. Given a plain-text English prompt, it drafts
requirements that conform to the INCOSE writing rules and a SysML block
definition diagram, traces one to the other, and meters what the generation
cost in tokens, seconds, and dollars. This transforms previously manual systems engineering processes into efficient and engineered models.
Hope you enjoy the read and get a chance to test it out on your local machine!

Conversation is the way in. You describe a system in chat; it retrieves from
the project knowledge base first, asks about whatever the documents do not
settle, and drafts requirements grounded in what the documents actually say.
Those requirements are the working set — editable by hand — and the block
diagram is generated from them with no second prompt. Committing anything to
the model re-indexes it, so what the tool generates becomes what the tool
retrieves.

Five things happen to every generated artifact:

1. **Retrieval** over two sources — system documents you load, and the MBSE
   model being built — so generation starts from project fact rather than from
   the sentence it was handed.
2. **Lexical validation** against the INCOSE writing rules, with failures
   driving a targeted rewrite rather than a rejection.
3. **Semantic review** by a second model, scoring what a regex cannot see, such as
   whether a requirement is singular, verifiable, and implementation-free.
4. **Traceability** linking requirements to the design elements that satisfy
   them, which makes coverage gaps computable.
5. **Metering** of tokens, latency, conformance, and cost on every call.

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

Diagram generation also reads whatever requirements you have kept, so the design
follows from them rather than being drafted alongside them. On a ground station
example this took the proposed trace links from 5 to 10 and dropped the blocks
satisfying no requirement from 7 to 1.

---

## Architecture

```
┌──────────────┐   HTTP/JSON   ┌────────────────┐   ┌─────────────────┐
│  React (SPA) │ ────────────▶ │  FastAPI       │──▶│ Ollama (local)  │
│  :5173       │ ◀──────────── │  :8000         │   │ generate+embed  │
└──────────────┘               │                │   └─────────────────┘
                               │  llm.py routes │   ┌─────────────────┐
                               │  by model id   │──▶│ Anthropic API   │
                               └───────┬────────┘   └─────────────────┘
                                       ▼
                               data/mappy.db
     (model elements, diagram, traces, documents, rag_chunks, activity + eval logs)
```

`llm.py` dispatches on the model id and both providers return the same result
shape, so the rule engine, repair loop, and metrics are provider-agnostic.
`claude-*` goes to the Anthropic SDK; anything else goes to Ollama.

### The retrieval loop

```
   system documents ──chunk──┐
                             ├──▶ rag_chunks ──▶ retriever ──▶ chat / diagram
   MBSE model ──────chunk────┘      (vectors)                        │
        ▲                                                            │
        └──────────── committed requirements and blocks ─────────────┘
```

Two knowledge sources feed one index. `rag.py` holds the chunking and scoring
with no database dependency; `knowledge.py` wires it to storage and is the one
place that decides when the index is rewritten.

- **Chunking is heading-aware.** Engineering documents are sectioned because
  each section is a separable concern, so a heading is a better boundary than
  a word count. Every chunk carries its document title and its own heading —
  without that, a chunk about a 20-minute holding time never says what is
  being held up, and a search for "backup power" cannot find it.
- **Model elements are chunked for how they get searched.** A requirement
  carries its stereotype and verify method, because "which requirements are
  verified by test" is a real query. A block carries the interfaces it sits
  on, because a block name alone says almost nothing.
- **Embeddings are local**: `nomic-embed-text` through Ollama, 768 dimensions,
  cosine similarity, top 6, floor at 0.30. Below that floor a chunk is noise,
  and padding a prompt with noise is how a grounded answer becomes a
  confidently wrong one.
- **Lexical scoring is the fallback**, not the design. If Ollama is
  unreachable the index still answers by term overlap and the UI says which
  method ran, so a missing embedding model degrades retrieval instead of
  breaking the app.

---

## Quickstart

Requires Python 3.12+, Node 18+, and [Ollama](https://ollama.com).

```bash
ollama pull llama3.1:8b        # ~4.9 GB, one time — generation
ollama pull nomic-embed-text   # ~274 MB, one time — embeddings for retrieval
./scripts/dev.sh
```

Ollama is needed even when generating with a hosted Claude model, because
embeddings always run locally. Without it, retrieval falls back to keyword
matching and the Knowledge tab says so.

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
  rag.py              chunking, embedding, scoring -- no database dependency
  knowledge.py        wires rag.py to storage; owns when the index is rebuilt
  prompts.py          system instructions, retrieval guidance, repair prompts
  rules.py            INCOSE rule engine (8 checks + duplicate detection)
  diagram_rules.py    SysML structural/referential validation
  traceability.py     satisfy/refine/verify links + coverage analysis
  judge.py            semantic review scoring, cross-tabbed with the rules
  evaluation.py       metrics, cost model, aggregation
  eval_suite.py       golden prompt set
  storage.py          SQLite persistence
  seed_docs/          bundled reference corpus (fictional Meridian program)
  routes/             chat, documents, requirements, diagram, traces,
                      evaluations, models, elements, log
frontend/src/
  components/         ChatPanel, RequirementsWorkbench, KnowledgePanel,
                      BlockDiagram, EvaluationsPanel, TraceabilityPanel,
                      ModelElementsPanel, ActivityLog
  DiagramPage.jsx     standalone full-size diagram route
scripts/
  dev.sh              setup + start both servers, wait until each answers
  stop.sh             stop both servers
```

```bash
cd backend && pytest app/tests -q    # 55 tests: rules, rag, traceability, judge
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
  round-trip into Cameo or Rhapsody. The MBSE side of the retrieval index is
  therefore the model *this tool* builds, not a parsed Cameo model. Blocks are
  already chunked with their interfaces folded in, which is the shape a Cameo
  parser would need to produce, but the parser itself is not written.
- **Retrieval can be confidently irrelevant.** Similarity search returns the
  nearest chunks, not the correct ones, and a question the corpus does not
  answer still returns its six best guesses. The floor at 0.30 drops the worst
  of it and the prompt tells the model to ignore passages that do not bear on
  the question, but neither is a guarantee. Every answer names the passages it
  used so the engineer can check rather than trust.
- **Documents must be UTF-8 text.** `.txt` and `.md` are parsed; PDF and Word
  are rejected with a message rather than indexed as mojibake.
- **Duplicate detection is string similarity**, so it catches restatements, not
  two differently-worded requirements that mean the same thing.
- **Local SQLite database** — single user, no auth. Everything goes through
  `storage.py`, so pointing it at a server database touches one module.
