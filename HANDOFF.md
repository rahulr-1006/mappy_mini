# Mini-MAPPy — Agent Handoff

Context for an agent picking up this repo cold. Read `README.md` first for what
the project does; this covers what the README does not: why things are the way
they are, and what will bite you.

## What it is

AI-assisted MBSE tool. Takes a plain-English system description and produces
(a) requirements conforming to INCOSE writing rules and (b) a SysML block
definition diagram. Both are validated programmatically and repaired via
targeted re-prompting. Requirements trace to design blocks. A second model
reviews requirement substance. Every generation is metered.

Built as a demo for a job interview on 2026-09-14 — a project director, a tech
lead, and a lead SWE, who will review the repo directly.

## Stack

- **Backend**: FastAPI + Pydantic 2 + uvicorn, Python 3.14 venv at `backend/venv`
- **Frontend**: React 19 + Vite 8, React Flow (`@xyflow/react`) for diagrams, oxlint
- **Models**: Ollama (`llama3.1:8b`) local, Anthropic SDK 1.5.0 hosted
- **Storage**: single JSON file, `backend/data/state.json`

## Run it

```bash
./scripts/dev.sh        # setup if needed, start both, wait until each answers
./scripts/stop.sh       # stop both
```

`localhost:5173`. Ollama runs as a brew background service. Standalone diagram
view at `/diagram-view`.

Don't start the servers by hand unless you have a reason. The frontend fetches
once on mount, so starting it before the API answers produces a "Load failed"
banner that never retries — `dev.sh` waits on `/health` to make that race
impossible. It's also idempotent: re-running it clears the ports first.

Checks: `cd backend && pytest app/tests -q` (23 tests) ·
`cd frontend && npx oxlint src/ && npx vite build`

## Architecture

`llm.py` dispatches by model id: `claude-*` → `anthropic_client.py`, anything
else → `ollama_client.py`. Both return `LLMResult`. Everything downstream is
provider-agnostic.

Prompt builders return `(system, user)` tuples, not one string. The system half
is invariant and marked cacheable; the user half carries the request. Every
call site must pass both.

Generation flow (requirements and diagrams both follow it):
1. Build prompt (`prompts.py`)
2. Call model, parse JSON tolerantly (models return 3+ different shapes)
3. Validate — `rules.py` (lexical) or `diagram_rules.py` (referential)
4. On violation, re-prompt with the specific violations, bounded by
   `config.MAX_REPROMPTS = 3`
5. Roll all calls into one metrics record → `storage.add_eval_record()`

Requirements repair **one item at a time**; diagrams repair **the whole object**
(violations are graph properties, not node properties).

Beyond generation: `traceability.py` computes coverage from satisfy links,
`judge.py` scores requirement substance and cross-tabs it against the rule
engine, `eval_suite.py` runs a fixed 6-prompt benchmark.

## Decisions worth not undoing

Each of these looks like a candidate for cleanup and would reintroduce a bug or
lose a property.

- **Cost is derived at read time** from stored token counts, not frozen per
  record — so a rate correction reprices history. Don't cache cost into records.
- **`_extract_json` decodes the first complete JSON value** rather than parsing
  the whole response. Claude sometimes emits valid JSON followed by a closing
  fence and a prose rationale. An end-anchored fence strip does not handle that.
- **`_parse_requirement_array` handles a single bare requirement object.** The
  eval suite caught this — 2 of 3 prompts produced zero output without it.
- **`normalize_review` scores an absent criterion 0, not 1.** Zero is excluded
  from the mean; 1 would silently drag a requirement to the floor when the judge
  omits a field. A test pins this.
- **Only `satisfy` counts toward coverage.** Refining or verifying a requirement
  does not mean anything fulfils it. A test pins this too.
- **Composition edges are deliberately unlabeled** in `BlockDiagram.jsx`. With
  most blocks hanging off the root, labeling each buried the diagram in
  overlapping text; tree position already conveys containment.
- **React Flow needs `useNodesState`/`onNodesChange`** or dragging silently
  no-ops. Don't revert to passing plain `nodes` props.
- **Same-row diagram edges arc below the row** (bottom-to-bottom handles) so
  they don't cut through intervening boxes.
- **Prompt caching is left in place even though it currently no-ops.** The
  prefix is below the model's minimum cacheable length. Do not pad the prompt
  to cross that threshold — paying for filler input tokens to earn a discount on
  those same tokens loses money. It starts paying if instructions genuinely grow.
- **`storage.py` isolates persistence** so the JSON file can be swapped for a
  real DB in one module. Keep that boundary.

## Constraints

- **No `Co-Authored-By: Claude` or `Claude-Session:` trailers** in commits or
  PRs. The user had these stripped from all history. Message body only.
- **`backend/.env` holds a live Anthropic API key** and is gitignored. Never
  commit it, never echo it. `.env.example` documents the shape.
- Hosted calls cost real money. Get approval before running the golden suite
  against a hosted model (~$0.09/run on Haiku, more on Sonnet/Opus).
- Repo is `github.com/rahulr-1006/mappy_mini`, branch `main`.

## State

Committed and pushed, working tree clean. The app carries demo data: kept
requirements, a saved launch-vehicle diagram, accepted trace links, and an eval
log including a local-vs-hosted benchmark.

`backend/data/state.json` is gitignored — it holds that demo data plus the eval
log. **Don't wipe it without backing up**; the benchmark history costs real
money and time to reproduce.

Watch for drift between the requirements and the diagram: they are independent
collections, and generating a diagram for a different system leaves traceability
comparing unrelated artifacts. (The model correctly proposes nothing in that
case, which is a useful behaviour but a confusing demo.)

## Benchmark results (golden suite, same 6 prompts)

| | `llama3.1:8b` | `claude-haiku-4-5` |
|---|---|---|
| Requirements | 11 | 32 |
| Diagram blocks | 22 | 30 |
| First-pass rate | 50% | 63% |
| Final success rate | 93% | 97% |
| Wall clock | 290s | 136s |
| Cost | free | $0.0910 |

The 50% → 93% lift is the headline: self-correction is worth 43 points of
conformance and lets an 8B local model land within 4 points of a hosted model.

Second headline: on the current model elements, **2 of 5 requirements passed
every lexical rule but were flagged by semantic review**, both for bundling
multiple needs. That bounds what lexical validation is worth.

## Not done

- No SysML XMI export (can't round-trip into Cameo/Rhapsody)
- Trace links are requirement→block only; no requirement→requirement `derive`
- Duplicate detection is string similarity, not semantic
- No streaming — a 60s generation shows only a disabled button
- Single user, no auth, no concurrent writers
- Diagram edges are labeled lines, not UML glyphs (no filled diamonds)
- No CI
- `mistral:7b` is in `config.AVAILABLE_MODELS` but was never pulled
