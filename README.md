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

**The rulebook is executable.** `rules.py` implements eight requirement
checks, plus a batch-level near-duplicate detector and one advisory, each
carrying a stable id and the INCOSE quality characteristic it serves:

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

Diagrams get the same treatment with different rules, in the same file.
Validation there is referential integrity, and repair re-prompts the whole
graph rather than one node. Diagram generation also reads whatever
requirements you have kept, so the design follows from them rather than being
drafted alongside them. On a ground station example this took the proposed
trace links from 5 to 10 and dropped the blocks satisfying no requirement
from 7 to 1.

---

## Working from their papers

MAPPy is a production tool. It has a full stack behind it, a real database, and
an API into the MagicDraw tooling where MBSE work actually happens. None of
that is here. This is a weekend build of one slice, the generation pipeline,
and it stops well before the integration work starts.

The published evaluation is what I had to work from. The papers are direct
about where their own results were weak, which makes them a good place to try
things. Four of those are prototyped below. They are starting points rather
than answers, and each one has a part I would want to work through with people
who know the tool.

**Malformed output.** A model that wraps its array in prose breaks the parser,
and the whole batch goes with it. This seemed worth separating from a rule
violation, since the content can be fine while only the envelope is wrong. Two
layers: Ollama runs with `format="json"`, and because the Messages API has no
equivalent switch, `_extract_json` strips a markdown fence and uses
`raw_decode` to take the first complete value. When parsing still fails,
`_parse_with_recovery` asks again for the envelope alone, bounded at two
attempts and counted in the metrics.

*Future Implementation:* the recovery spends a whole extra call on what is
usually a formatting slip. Repairing the common cases locally before paying for
a call would probably handle most of them, and I have not measured how often
the retry is the thing that actually saves a batch.

**Which rule broke, rather than pass or fail.** Every violation carries a
stable id, the INCOSE quality characteristic it serves, and the offending
text, so a failure says what to change. That is also what makes the targeted
retry possible, since the repair prompt can name the specific rules broken.

*Future Implementation:* ten checks is a starting set, and the term lists
inside them are my reading of the guidance rather than anything authoritative.
A systems engineer would want to tune both, which is why they are plain data at
the top of `rules.py`, but tuning them through a config rather than a code edit
is the obvious next step.

**Harmful or biased content.** Their published material names this as a
limitation of the underlying model, and I could not find it addressed there. A
profanity or toxicity list over satellite requirements did not seem like it
would catch anything real. What I tried instead reads bias as a
systems-engineering concern: a requirement that fixes a human capability, a
lifting weight or a reach or an acuity or "unaided", without naming an
anthropometric, ergonomic, or accessibility standard has made a decision about
who can operate the system without saying so. `MM-R10` flags that. Two choices
around it matter more than the check:

- It is an advisory rather than a rule failure, so it never gates whether a
  requirement counts as clean.
- It never goes to the repair loop. A model told to fix an exclusionary
  constraint will usually delete it, and quietly dropping an accessibility
  consideration is worse than stating one badly. The objection is to the limit
  being unjustified, not to the limit existing, so naming a standard clears
  it. That is a judgement for a person, which is why `ADVISORY_RULES` is kept
  separate from `RULES`.

*Future Implementation:* this is my interpretation of a limitation they name in
a single line, and it may not be what they meant by it. The check is also a
keyword heuristic underneath, so it will miss an exclusionary requirement
phrased without the words it looks for. I would want to know whether the
framing is even the right one before building on it.

**Controlled model comparison.** The provider table elsewhere in this README is
assembled from whatever happens to be in the evaluation log, which compares
runs that were never controlled against each other. **Head to head** runs one
prompt through each configured model back to back instead. Measured on a
satellite ground station prompt:

| Model | Requirements | First pass | Valid after repair | Latency | Cost |
|---|---|---|---|---|---|
| claude-haiku-4-5 | 12 | 17% | 100% | 30.5s | $0.0195 |
| llama3.1:8b | 1 | 0% | 100% | 16.4s | free |

Output volume differs by an order of magnitude and neither model wrote a
conformant requirement on the first pass, but both end up in the same place
after repair.

*Future Implementation:* this is one prompt and one run per model. The inputs
are controlled, but the numbers still move when you re-run it. Several prompts
and several runs per cell would be needed before treating any of this as a
benchmark.

**What is not addressed.** Scope stops at requirements and blocks, since
extending it touches the schema, the validator, and the UI together. Their
roadmap items, relationship-gap detection, test case generation, and
automatic diagram assembly, are not built. Neither is anything on the
integration side, which is most of what makes MAPPy a tool rather than a
pipeline.

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

Ten modules, each one a single concern:

```
backend/app/
  main.py
  config.py
  models.py
  llm.py
  prompts.py
  rules.py
  rag.py
  knowledge.py
  evaluation.py
  storage.py
  seed_docs/
  routes/
  tests/
frontend/src/
  api.js
  App.jsx
  components/
  DiagramPage.jsx
demo_documents/
scripts/
  dev.sh
  reset.sh
  stop.sh
```

Two boundaries are load-bearing and worth the extra file. `rag.py` has no
database dependency, which is what makes chunking and scoring testable
without one; `knowledge.py` is the only place that decides when the index is
rewritten. Everything else is grouped by what it is for rather than split by
how big it got: both LLM providers sit behind one dispatcher in `llm.py`,
and every non-LLM validity check, requirement wording, diagram structure,
and trace links, is in `rules.py`, because they all feed the same repair loop.

```bash
cd backend && pytest app/tests -q    # 67 tests: rules, rag, prompts, recovery, review, storage
cd frontend && npx oxlint src/ && npx vite build
```

---

## Limitations

Stated plainly, because they bound what this is useful for.

Nothing here establishes that a requirement is *correct*. The rule engine only
checks how a requirement is written. The semantic reviewer goes further,
catching requirements that bundle several needs together or cannot be tested
objectively, but the reviewer is itself a language model, not ground truth. It
is non-deterministic, it can be wrong, and it has no visibility into the
stakeholder need the requirement is supposed to serve. Treat its scores as a
prioritised reading list for a human, not a pass-or-fail gate. A person still
promotes each requirement into the model. What the tool removes is the drudgery
of checking conformance by hand, not the engineer's judgement.

The rule engine has two limits of its own worth naming. The 40-word minimum is
a proxy rather than a literal INCOSE rule, a cheap stand-in for completeness;
the vague-terms, absolutes, and escape-clause checks map far more directly to
the guidance. All the term lists are plain data at the top of `rules.py`, so a
systems engineer can tune them without touching the logic. Duplicate detection
is string similarity, which catches a requirement restated in nearly the same
words but not two differently-worded requirements that happen to mean the same
thing.

The same caution applies to trace links. The model proposes them from
overlapping wording between a requirement and a block description, so they are
inferred rather than derived from anything structural. Hallucinated ids are
dropped before display, but a link can still look plausible and be wrong, which
is exactly why nothing is written into the model until a person accepts it.

There is no SysML interchange. Output is application JSON, not XMI, so nothing
round-trips into Cameo or Rhapsody. The MBSE side of the retrieval index is
therefore the model *this tool* builds, not something parsed out of an actual
Cameo project. Blocks are already chunked with their interfaces folded in,
which is the shape a Cameo parser would need to produce, but that parser is not
written.

Retrieval has the failure mode every similarity search has: it returns the
nearest chunks, not necessarily the correct ones. Ask it something the corpus
does not answer and it still hands back its six best guesses rather than
admitting it does not know. The floor at 0.30 drops the worst of that, and the
prompt tells the model to ignore passages that do not bear on the question, but
neither is a guarantee. Every answer names the passages it drew from, so the
engineer can check the source rather than trust the output.

Two operational constraints round it out. Documents must be UTF-8 text: `.txt`
and `.md` are parsed, while PDF and Word are rejected with a message rather
than indexed as mojibake. And the database is local SQLite, single user, no
auth. Everything goes through `storage.py`, so pointing it at a server database
touches one module.

---

Overall it was a fun project to reproduce, and I would love to get insight from
the developers themselves on their architecture as well as improvements.
