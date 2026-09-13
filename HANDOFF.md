# Mini-MAPPy — Agent Handoff

Context for an agent picking up this repo cold.

## What it is

AI-assisted MBSE tool. Takes a plain-English system description and produces
(a) requirements conforming to INCOSE writing rules, and (b) a SysML block
definition diagram. Both are validated programmatically and repaired via
targeted re-prompting. Every generation is metered (tokens, latency, cost).

Built as a demo for a job interview on 2026-09-14. The audience is a project
director, a tech lead, and a lead SWE, who will review the repo directly.

## Stack

- **Backend**: FastAPI 0.141 + Pydantic 2.13 + uvicorn, Python 3.14 venv at `backend/venv`
- **Frontend**: React 19 + Vite 8, React Flow (`@xyflow/react` 12) for diagrams, oxlint
- **Models**: Ollama (`llama3.1:8b`) local, Anthropic SDK 1.5.0 hosted
- **Storage**: single JSON file, `backend/data/state.json`

## Run it

```bash
# backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm run dev
```

`localhost:5173`. Ollama runs as a brew background service. Standalone diagram
view at `/diagram-view`.

Checks: `cd backend && pytest app/tests -q` (12 tests) ·
`cd frontend && npx oxlint src/ && npx vite build`

## Architecture

`llm.py` dispatches by model id: `claude-*` → `anthropic_client.py`, anything
else → `ollama_client.py`. Both return `LLMResult(text, prompt_tokens,
completion_tokens, duration_ms)`. Everything downstream is provider-agnostic.

Generation flow (both routes follow it):
1. Build prompt (`prompts.py`) — rules embedded in the system instruction
2. Call model, parse JSON tolerantly (models return 3+ different shapes)
3. Validate — `rules.py` for requirements (lexical), `diagram_rules.py` for
   diagrams (referential integrity)
4. On violation, re-prompt with the specific violations, bounded by
   `config.MAX_REPROMPTS = 3`
5. Roll all calls into one metrics record → `storage.add_eval_record()`

Requirements repair **one item at a time**; diagrams repair **the whole object**
(violations are graph properties, not node properties).

## Decisions worth not undoing

- **Cost is derived at read time** from stored token counts, not frozen per
  record — so a rate correction reprices history. Don't "optimize" this by
  caching cost into records.
- **Composition edges are deliberately unlabeled** in `BlockDiagram.jsx`. With
  most blocks hanging off the root, labeling each buried the diagram in
  overlapping text. Tree position already conveys containment.
- **React Flow needs `useNodesState`/`onNodesChange`** or dragging silently
  no-ops. This was a real bug; don't revert to passing plain `nodes` props.
- **Same-row diagram edges arc below the row** (bottom-to-bottom handles) so
  they don't cut through intervening boxes.
- **`_parse_requirement_array` handles a single bare requirement object.** The
  eval suite caught this — 2 of 3 prompts were producing zero output without it.
- **`storage.py` isolates persistence** so the JSON file can be swapped for a
  real DB in one module. Keep that boundary.

## Constraints

- **No `Co-Authored-By: Claude` or `Claude-Session:` trailers** in commits or
  PRs. The user had these stripped from all history. Message body only.
- **`backend/.env` holds a live Anthropic API key** and is gitignored. Never
  commit it, never echo it. `.env.example` documents the shape.
- Hosted calls cost real money. Get approval before running the golden suite
  against a hosted model (~$0.09/run on Haiku, more on Sonnet/Opus).
- Repo is pushed to `github.com/rahulr-1006/mappy_mini`, branch `main`.

## State

Committed and pushed: 11 commits, working tree clean. The app is loaded with
demo data (5 kept requirements, a saved 12-block launch vehicle diagram, 29
eval records including a local-vs-hosted benchmark).

`backend/data/state.json` is gitignored — it holds that demo data plus the eval
log. Don't wipe it without backing up; the benchmark history is not
reproducible for free.

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

## Not done

- No traceability links between requirements and diagram blocks
- No SysML XMI export (can't round-trip into Cameo/Rhapsody)
- Duplicate detection is string similarity, not semantic
- No streaming — a 60s generation shows only a disabled button
- Single user, no auth, no concurrent writers
- Diagram edges are labeled lines, not UML glyphs (no filled diamonds)
- `mistral:7b` is in `config.AVAILABLE_MODELS` but was never pulled
