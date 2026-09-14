# Mini-MAPPy

**DEMO:** https://youtu.be/kb3O7bzeyWg

AI-assisted MBSE tooling, based on MAPPy by Booz Allen Hamilton.

You describe a system in chat. The tool retrieves from a project knowledge base,
asks about whatever the documents do not settle, and drafts requirements that
conform to the INCOSE writing rules. Those requirements are the working set and
you edit them by hand. The SysML block diagram is then generated from them, with
no second prompt. It traces one to the other and meters what every call cost in
tokens, seconds, and dollars.

Runs against a local model through [Ollama](https://ollama.com) by default, or
against the hosted Anthropic API using the same pipeline.

---

## Quickstart

Requires Python 3.12+, Node 18+, and [Ollama](https://ollama.com).

```bash
ollama pull llama3.1:8b        # ~4.9 GB, one time, generation
ollama pull nomic-embed-text   # ~274 MB, one time, embeddings for retrieval
./scripts/dev.sh
```

`dev.sh` creates the virtualenv and installs both dependency sets on first run,
frees the ports if something is already on them, starts the API and the dev
server, waits until each actually answers, and opens the app.

- App: <http://localhost:5173>
- Full-size diagram: <http://localhost:5173/diagram-view>
- API docs: <http://localhost:8000/docs>

```bash
./scripts/dev.sh --no-open
./scripts/reset.sh              # clear a demo run, keep the documents
./scripts/stop.sh
tail -f /tmp/mappy-backend.log
```

Ollama is needed even when generating with a hosted Claude model, because
embeddings always run locally. Without it, retrieval falls back to keyword
matching and the Knowledge tab says so.

To use a hosted model, copy `backend/.env.example` to `backend/.env` and set
`ANTHROPIC_API_KEY`. Claude models then appear in the model picker alongside the
local ones.

<details>
<summary>Running the servers by hand</summary>

```bash
# terminal 1
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# terminal 2, only after the API answers on :8000
cd frontend
npm install
npm run dev
```

</details>

---

## What happens to every generated artifact

1. **Retrieval** over two sources, the system documents you load and the MBSE
   model being built, so generation starts from project fact rather than from
   the sentence it was handed.
2. **Lexical validation** against the INCOSE writing rules, where failures drive
   a targeted rewrite rather than a rejection.
3. **Semantic review** by a second model, scoring what a regex cannot see, such
   as whether a requirement is singular, verifiable, and implementation-free.
4. **Traceability** linking requirements to the design elements that satisfy
   them, which makes coverage gaps computable.
5. **Metering** of tokens, latency, conformance, and cost on every call.

Committing anything to the model re-indexes it, so what the tool generates
becomes what the tool retrieves.

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
     (model elements, diagram, traces, documents, rag_chunks, chat, activity + eval logs)
```

`llm.py` dispatches on the model id and both providers return the same result
shape, so the rule engine, repair loop, and metrics are provider-agnostic.
`claude-*` goes to the Anthropic SDK, anything else goes to Ollama.

`data/mappy.db` is runtime state, not source. It is gitignored and created on
first run by `storage.py`, so a fresh clone has no database until the backend
starts. Use `./scripts/reset.sh` to clear it rather than deleting the file,
which would leave the running server pointing at a deleted inode.

### The retrieval loop

```
   system documents ──chunk──┐
                             ├──▶ rag_chunks ──▶ retriever ──▶ chat / diagram
   MBSE model ──────chunk────┘      (vectors)                        │
        ▲                                                            │
        └──────────── committed requirements and blocks ─────────────┘
```

Two knowledge sources feed one index. `rag.py` holds the chunking and scoring
with no database dependency. `knowledge.py` wires it to storage and is the one
place that decides when the index is rewritten.

- **Chunking is heading-aware.** Engineering documents are sectioned because
  each section is a separable concern, so a heading is a better boundary than a
  word count. Every chunk carries its document title and its own heading.
  Without that, a chunk about a 20-minute holding time never says what is being
  held up, and a search for "backup power" cannot find it.
- **Model elements are chunked for how they get searched.** A requirement
  carries its stereotype and verify method, because "which requirements are
  verified by test" is a real query. A block carries the interfaces it sits on,
  because a block name alone says almost nothing.
- **Embeddings are local:** `nomic-embed-text` through Ollama, 768 dimensions,
  cosine similarity, top 6, floor at 0.30. Below that floor a chunk is noise,
  and padding a prompt with noise is how a grounded answer becomes a confidently
  wrong one.
- **Lexical scoring is the fallback,** not the design. If Ollama is unreachable
  the index still answers by term overlap and the UI says which method ran, so a
  missing embedding model degrades retrieval instead of breaking the app.

---

## Why this is more than one LLM call

An LLM asked for INCOSE-conformant requirements will produce plausible prose
that quietly breaks the rules. This project treats that as the engineering
problem rather than the finished product.

**The rulebook is executable.** `rules.py` implements eight checks, plus a
batch-level near-duplicate detector and one advisory, each carrying a stable id
and the INCOSE quality characteristic it serves:

| id | check | characteristic |
|---|---|---|
| MM-R01 | minimum length | Complete |
| MM-R02 | presence of "shall" | Conforming |
| MM-R03 | vague terms | Unambiguous |
| MM-R04 | unachievable absolutes | Feasible |
| MM-R05 | bare pronouns | Unambiguous |
| MM-R06 | escape clauses | Verifiable |
| MM-R07 | open-ended clauses | Complete |
| MM-R08 | superfluous phrases | Concise |
| MM-R09 | near-duplicate (batch level) | Unique |
| MM-R10 | unjustified human limit (advisory) | Necessary |

The identifiers are deliberately ours rather than INCOSE rule numbers. The eight
quality characteristics in INCOSE-TP-2010-006-04 are stable and quotable, its
rule numbering is not something worth asserting from memory in front of someone
who knows the standard. `RULE_CATALOG` maps each check to the characteristic it
serves, which is the claim that can actually be defended.

**Violations drive a targeted retry.** A failing requirement is re-prompted with
*the specific rules it broke*, not a generic "try again", bounded at three
attempts so worst-case cost stays bounded.

**The loop's value is measured, not asserted.** On the benchmark suite, locally
generated requirements pass all rules first try **50%** of the time and are
valid after self-correction **93%** of the time. That 43-point lift is what the
validation layer buys.

Diagrams get the same treatment with different rules. Validation there is
referential integrity, and repair re-prompts the whole graph rather than one
node. Diagram generation also reads whatever requirements you have kept, so the
design follows from them rather than being drafted alongside them. On a ground
station example this took the proposed trace links from 5 to 10 and dropped the
blocks satisfying no requirement from 7 to 1.

---

## Shortcomings in the source material, and what was done about them

The MAPPy papers name specific weaknesses in their own evaluation. Those are the
most useful thing in the source material, because they say where the work
actually was.

| Named weakness | What this build does |
|---|---|
| Malformed output, distinct from bad content | Prevented and recovered, see below |
| Which rule broke, not just pass or fail | Every violation carries a stable id, characteristic, and offending text |
| Latency per call | Captured on every `LLMResult`, shown per row and per provider |
| Harmful or biased content | Reframed as `MM-R10`, an advisory, see below |
| Controlled model comparison | **Head to head** runs one prompt through every configured model back to back |
| Limited to requirements and blocks | Not addressed, same limitation here |

**Malformed output.** Their promptfoo results report responses that "include
text before table formatting", meaning the model wrapped its array in prose and
broke the parser. That is a different failure from a rule violation and needs a
different fix, because the content may be fine and only the envelope is wrong.
Handled in two layers. *Prevention:* Ollama runs with `format="json"`, which is
a hard guarantee, and the Anthropic path has no such switch so `_extract_json`
strips a markdown fence and uses `raw_decode` to take the first complete value
and discard trailing commentary. *Recovery:* when parsing still fails,
`_parse_with_recovery` re-prompts for the envelope alone, bounded at two
attempts and counted in the metrics. Previously one stray sentence of preamble
discarded every requirement in the response.

**Harmful or biased content.** The 2023 deck lists this as a limitation of the
underlying model that MAPPy has to work around, and the source material does not
show it being addressed. A profanity or toxicity keyword list over satellite
requirements would be box-ticking. The version built here treats bias as the
systems-engineering problem it actually is: a requirement that fixes a human
capability (a lifting weight, a reach, an acuity, "unaided") without naming an
anthropometric, ergonomic, or accessibility standard has silently decided who is
allowed to operate the system. `MM-R10` flags that, and two design decisions
matter more than the check itself:

- It is an **advisory, not a rule failure**. It never gates whether a
  requirement counts as clean.
- It is **never sent to the repair loop**. A model told to fix an exclusionary
  constraint will delete it, and silently dropping an accessibility
  consideration is worse than stating one badly. The check objects to the limit
  being unjustified, not to the limit existing, so naming a standard clears it.
  That is a judgement for a person, which is why `ADVISORY_RULES` is kept
  separate from `RULES`.

**Head to head**, measured on a satellite ground station prompt:

| Model | Requirements | First pass | Valid after repair | Latency | Cost |
|---|---|---|---|---|---|
| claude-haiku-4-5 | 12 | 17% | 100% | 30.5s | $0.0195 |
| llama3.1:8b | 1 | 0% | 100% | 16.4s | free |

Read the first two columns together. Output volume differs by an order of
magnitude and neither model wrote a conformant requirement on the first pass.
What the repair loop buys is that both land in the same place.

Scoping to requirements and blocks was deliberate, since extending it touches
the schema, the validator, and the UI together. Their roadmap items,
relationship-gap detection, test case generation, and automatic diagram
assembly, are not built either, and are not claimed.

---

## Evaluation

Every generation records tokens in and out, LLM call count including each repair
attempt, wall clock, items produced, first-pass conformance, and final
conformance. Cost is derived at read time from stored token counts, so
correcting a published rate reprices history rather than leaving stale figures
baked into old records.

A fixed golden set of six prompts, three for requirements and three for
diagrams, re-runs on demand, so a prompt or model change is compared on
identical inputs. [REPRODUCE.md](REPRODUCE.md) maps every number below to the
command that produced it, and says which of them survive a re-run:

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
what my machine could computationally do in the scope of a weekend.

**Semantic review.** The rule engine is lexical. It verifies a requirement is
*written* well, it cannot tell you whether the requirement bundles three needs
into one sentence, or states something no test could falsify. A second model
scores the same requirements on criteria a regex cannot reach and the two
signals are cross-tabulated.

**What the evals caught.** Their first run exposed a silent failure that manual
testing had missed. The requirements parser assumed a JSON array, but the model
sometimes returns a single bare requirement object, and the whole generation was
being discarded. Two of three requirements prompts were producing nothing. The
fix was four lines, and the same suite verified it.

---

## Traceability

Requirements and design elements are only useful together. The app links them
with SysML relationships such as `satisfy`, `refine`, and `verify`, then
computes the two findings that matter in a design review:

- **Uncovered requirements**, agreed, written down, and allocated to nothing
  that builds them. Only `satisfy` counts here, since refining or verifying a
  requirement does not mean anything fulfils it.
- **Orphan blocks**, design elements that satisfy no stated requirement. Either
  a requirement is missing, or the element is unjustified scope.

The model proposes the matrix and a human confirms it. Suggestions are validated
against the real id sets before they are shown, so a hallucinated link is
dropped rather than surfaced, and nothing is written to the model until the
engineer accepts it. Asked to link requirements about a launch vehicle to a
diagram of an unrelated system, it correctly proposed nothing.

---

## Layout

```
backend/app/
  llm.py              provider router + shared result type
  ollama_client.py    local provider
  anthropic_client.py hosted provider
  rag.py              chunking, embedding, scoring, no database dependency
  knowledge.py        wires rag.py to storage, owns when the index is rebuilt
  prompts.py          system instructions, retrieval guidance, repair prompts
  rules.py            INCOSE rule engine (8 checks + duplicates + 1 advisory)
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
demo_documents/       a document to upload during a demo
scripts/
  dev.sh              setup + start both servers, wait until each answers
  reset.sh            clear a demo run
  stop.sh             stop both servers
```

```bash
cd backend && pytest app/tests -q    # 67 tests: rules, rag, format recovery, traceability, judge
cd frontend && npx oxlint src/ && npx vite build
```

---

## Limitations

There are some key limitation
Here's the limitations section rewritten as prose. I kept every point, just wrote it as full sentences and cut the bolded headline fragments:

---

**Limitations**

Nothing in this tool tells you a requirement is correct. The rule engine only checks how a requirement is written, and the semantic reviewer goes a step further by catching requirements that bundle several needs together or can't be tested objectively. But that reviewer is a language model, not ground truth. It's non-deterministic, it can be wrong, and it has no visibility into the actual stakeholder need a requirement is supposed to satisfy. I treat its output as a prioritized list for a human to read, not a pass or fail gate. A person still has to decide to promote each requirement into the model. What the tool removes is the drudgery of checking conformance by hand, not the engineer's judgment.

The same caution applies to trace links. The model proposes them by looking for overlapping wording between a requirement and a block description, so they're inferred, not derived from anything structural. I drop any hallucinated IDs before they're shown, but a link can still look plausible and be wrong, which is exactly why nothing gets written into the model until a person accepts it.

There's also no SysML interchange. The tool outputs plain JSON, not XMI, so nothing round-trips into Cameo or Rhapsody. That means the model side of the retrieval index is really the model this tool builds internally, not something parsed out of an actual Cameo project. I did chunk blocks with their interfaces folded in, which is the shape a Cameo parser would need to produce anyway, but I haven't written that parser.

Retrieval has the same failure mode every similarity search has: it returns the nearest chunks, not necessarily the right ones. Ask it something the corpus doesn't actually answer, and it will still hand back its six best guesses instead of admitting it doesn't know. I put a floor at 0.30 to cut the worst of that, and the prompt tells the model to ignore passages that don't bear on the question, but neither of those is a real guarantee. What I can guarantee is that every answer names the passages it drew from, so the engineer can go check the source instead of just trusting the output.

Overall it was a fun project to reproduce, and I would love to get insight from the developers themselves on their architecture as well as improvements.
