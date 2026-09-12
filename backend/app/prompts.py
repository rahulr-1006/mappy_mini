BASE_SYSTEM_INSTRUCTIONS = """You are a model-based systems engineer using SysML and the rules for writing requirements found in INCOSE-TP-2010-006-04. Requirements shall be necessary, implementation independent, unambiguous, complete, singular, feasible, correct, and conforming.

Requirements use the following stereotypes (capitalization matters): designConstraint, extendedRequirement, functionalRequirement, interfaceRequirement, performanceRequirement, physicalRequirement. Every requirement shall be verified by a verifyMethod: Analysis, Demonstration, Inspection, or Test.

Return ONLY a JSON array of objects, no other text before or after it. Each object shall have exactly these fields: "stereotype", "name", "text", "verifyMethod". "stereotype" shall not contain any spaces. "name" is a short summary of "text" and must contain spaces. Each "text" must meet the rules in INCOSE-TP-2010-006-04, have 40 or more words, include the word "shall", and be independently verifiable.

Do not use any of the following words or phrases: some, any, allowable, several, many, a lot of, a few, almost always, very nearly, nearly, about, close to, almost, approximate, so far as is possible, as little as possible, where possible, as much as possible, if it should prove necessary, as appropriate, as required, to the extent practical, including but not limited to, and so on, be designed to, be able to, be capable of, not, it, this, that, he, she, they, them, 100% reliability, 100% availability, all, every, always, never."""


def build_generation_prompt(desired_system: str) -> str:
    return (
        f"{BASE_SYSTEM_INSTRUCTIONS}\n\n"
        f"Generate a set of requirements for the following desired system:\n"
        f"{desired_system}"
    )


def build_reprompt(original_text: str, violations: list) -> str:
    violation_list = "; ".join(violations)
    return (
        f"{BASE_SYSTEM_INSTRUCTIONS}\n\n"
        f"Rewrite ONLY the following single requirement so that it no longer "
        f"breaks these rules: {violation_list}.\n"
        f"Original requirement text: \"{original_text}\"\n"
        f"Return a single JSON object (not an array) with fields "
        f"stereotype, name, text, verifyMethod."
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


def build_diagram_prompt(desired_system: str) -> str:
    return (
        f"{DIAGRAM_SYSTEM_INSTRUCTIONS}\n\n"
        f"Generate a block definition diagram for the following desired system:\n"
        f"{desired_system}"
    )


def build_diagram_reprompt(previous_json: str, violations: list) -> str:
    violation_list = "; ".join(violations)
    return (
        f"{DIAGRAM_SYSTEM_INSTRUCTIONS}\n\n"
        f"The following JSON object you previously returned breaks these rules: "
        f"{violation_list}.\n"
        f"Previous JSON: {previous_json}\n"
        f"Return a corrected JSON object with the same shape (\"blocks\" and "
        f"\"connectors\" fields) that fixes all of the listed problems."
    )
