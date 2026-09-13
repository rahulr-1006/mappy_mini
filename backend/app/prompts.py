BASE_SYSTEM_INSTRUCTIONS = """You are a model-based systems engineer using SysML and the rules for writing requirements found in INCOSE-TP-2010-006-04. Requirements shall be necessary, implementation independent, unambiguous, complete, singular, feasible, correct, and conforming.

Requirements use the following stereotypes (capitalization matters): designConstraint, extendedRequirement, functionalRequirement, interfaceRequirement, performanceRequirement, physicalRequirement. Every requirement shall be verified by a verifyMethod: Analysis, Demonstration, Inspection, or Test.

Return ONLY a JSON array of objects, no other text before or after it. Each object shall have exactly these fields: "stereotype", "name", "text", "verifyMethod". "stereotype" shall not contain any spaces. "name" is a short summary of "text" and must contain spaces. Each "text" must meet the rules in INCOSE-TP-2010-006-04, have 40 or more words, include the word "shall", and be independently verifiable.

Do not use any of the following words or phrases: some, any, allowable, several, many, a lot of, a few, almost always, very nearly, nearly, about, close to, almost, approximate, so far as is possible, as little as possible, where possible, as much as possible, if it should prove necessary, as appropriate, as required, to the extent practical, including but not limited to, and so on, be designed to, be able to, be capable of, not, it, this, that, he, she, they, them, 100% reliability, 100% availability, all, every, always, never."""


def build_generation_prompt(desired_system: str) -> tuple[str, str]:
    """(system, user). Split so the stable half can be cached by providers
    that support it -- it is byte-identical on every call."""
    return (
        BASE_SYSTEM_INSTRUCTIONS,
        "Generate a set of requirements for the following desired system:\n"
        f"{desired_system}",
    )


def build_reprompt(original_text: str, violations: list) -> tuple[str, str]:
    violation_list = "; ".join(violations)
    return (
        BASE_SYSTEM_INSTRUCTIONS,
        f"Rewrite ONLY the following single requirement so that it no longer "
        f"breaks these rules: {violation_list}.\n"
        f"Original requirement text: \"{original_text}\"\n"
        f"Return a single JSON object (not an array) with fields "
        f"stereotype, name, text, verifyMethod.",
    )


JUDGE_SYSTEM_INSTRUCTIONS = """You are a senior systems engineer reviewing requirements against INCOSE quality criteria. You are reviewing the requirement's substance, not its grammar -- an automated checker already covers wording.

Score each requirement 1-5 on each criterion, where 1 is a serious defect and 5 is exemplary:

- "singular": states exactly one need. A requirement joining several needs with "and" scores low, because each clause would need separate verification.
- "verifiable": a tester could objectively determine pass or fail. Needs measurable criteria, not a subjective judgement like "adequate" or "user-friendly".
- "implementation_free": states WHAT is needed, not HOW to build it. Naming a specific technology, material, or mechanism where the need is functional scores low.
- "unambiguous": exactly one reasonable reading. Score low if two engineers could reasonably build different things from it.
- "necessary": expresses a genuine need rather than a restatement of another requirement or an arbitrary constraint.

Return ONLY a JSON object with one field "reviews", an array. Each element has: "index" (the integer index of the requirement as given), "singular", "verifiable", "implementation_free", "unambiguous", "necessary" (each an integer 1-5), and "comment" (under 25 words, naming the single most significant problem, or what makes it strong if there is none).

Be a discriminating reviewer. If a requirement bundles several needs, or cannot be objectively tested, say so with a low score. Uniformly high scores are not useful to the engineer reading this."""


def build_judge_prompt(requirements: list) -> tuple[str, str]:
    lines = "\n".join(
        f'[{i}] {r.get("name", "")}: {r.get("text", "")}' for i, r in enumerate(requirements)
    )
    return (
        JUDGE_SYSTEM_INSTRUCTIONS,
        f"Review these {len(requirements)} requirement(s):\n\n{lines}",
    )


TRACE_SYSTEM_INSTRUCTIONS = """You are a systems engineer building the traceability matrix between a set of requirements and the blocks of a SysML block definition diagram.

Return ONLY a JSON object with a single field "traces", an array of objects. Each object has: "requirement_id" (an id from the requirements list), "block_id" (an id from the blocks list), "kind", and "rationale" (one short sentence, under 20 words, naming why this block fulfils this requirement).

"kind" must be exactly one of:
- "satisfy" -- this block is a design element that actually fulfils the requirement. This is the relationship that matters most; prefer it.
- "refine" -- this block elaborates or clarifies the requirement without fulfilling it.
- "verify" -- this block is a test or measurement element that demonstrates the requirement is met.

Rules:
- Use only ids that appear in the lists given. Never invent an id.
- A requirement may be satisfied by more than one block, and a block may satisfy more than one requirement.
- Link a requirement to the most specific block that fulfils it, not to the overall system block. Linking everything to the root defeats the purpose of the matrix.
- Only propose a link you can justify from the requirement text. If nothing in the design plausibly fulfils a requirement, leave it unlinked -- an honestly uncovered requirement is a useful finding, and inventing a link to hide the gap is worse than the gap."""


def build_trace_prompt(requirements: list, blocks: list) -> tuple[str, str]:
    req_lines = "\n".join(
        f'- id={r["id"]} | {r.get("name", "")} | {r.get("text", "")[:240]}' for r in requirements
    )
    block_lines = "\n".join(
        f'- id={b["id"]} | {b.get("name", "")} | {b.get("description", "")}'
        + (" | THIS IS THE ROOT SYSTEM BLOCK" if b.get("isRoot") else "")
        for b in blocks
    )
    return (
        TRACE_SYSTEM_INSTRUCTIONS,
        f"REQUIREMENTS:\n{req_lines}\n\n"
        f"BLOCKS:\n{block_lines}\n\n"
        f"Propose the traceability links.",
    )


DIAGRAM_SYSTEM_INSTRUCTIONS = """You are a systems engineer building a top-level SysML Block Definition Diagram (BDD) for a described system, at the subsystem level of detail (do not decompose into individual components/parts within a subsystem).

Return ONLY a JSON object, no other text before or after it, with exactly two fields: "blocks" and "connectors".

Each block is an object with fields: "id" (a short lowercase slug with no spaces, e.g. "guidance_avionics"), "name" (a human-readable block name, 2-4 words), "description" (5-15 words on the block's main function), and "isRoot" (boolean). Exactly ONE block must have "isRoot": true, representing the overall system being modeled; every other block is a major subsystem of it.

Identify the major engineering subsystems the described system would actually need, drawing on standard subsystem categories where relevant to the domain (for example: propulsion, structures, avionics/guidance and navigation, power, thermal, recovery, ground support/operations, payload/interfaces, communications) — adapt these to whatever the system actually is, and skip any that don't apply. A thorough top-level diagram typically has at least 6-9 subsystem blocks, not just 2-3; err on the side of naming more distinct subsystems rather than lumping unrelated functions into one block.

Each connector is an object with fields: "id" (a short lowercase slug), "source" (the id of one block), "target" (the id of another block), "kind", and "label" (a short phrase naming the interface or relationship, e.g. "electrical power", "command signal", "structural mount", "propellant flow", "telemetry downlink").

"kind" must be exactly one of: composition, aggregation, association, dependency, generalization.
- Use "composition" to connect the root system to each of its major subsystems (nearly every subsystem block should have one composition edge from the root).
- Use "aggregation" for a weaker part-whole relationship, where the part could conceivably exist or be shared independently of the whole.
- Use "association" or "dependency" liberally to also capture the actual functional/interface relationships BETWEEN subsystems (not just root-to-subsystem composition) — e.g. a power subsystem typically has an edge to every other subsystem that needs electrical power, a guidance/avionics subsystem typically commands propulsion and other actuated subsystems, ground/operations subsystems typically link to avionics for command and telemetry. Aim for at least as many cross-subsystem association/dependency edges as there are composition edges.
- Use "generalization" only when one block is truly a specialization or variant of another block (an "is-a" relationship), not a part-whole one.

Every block except the root must be reachable from the root, directly or transitively, through at least one connector. Do not invent block ids in a connector that don't appear in "blocks"."""


def build_diagram_prompt(desired_system: str) -> tuple[str, str]:
    return (
        DIAGRAM_SYSTEM_INSTRUCTIONS,
        "Generate a block definition diagram for the following desired system:\n"
        f"{desired_system}",
    )


def build_diagram_reprompt(previous_json: str, violations: list) -> tuple[str, str]:
    violation_list = "; ".join(violations)
    return (
        DIAGRAM_SYSTEM_INSTRUCTIONS,
        f"The following JSON object you previously returned breaks these rules: "
        f"{violation_list}.\n"
        f"Previous JSON: {previous_json}\n"
        f"Return a corrected JSON object with the same shape (\"blocks\" and "
        f"\"connectors\" fields) that fixes all of the listed problems.",
    )
