import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

AVAILABLE_MODELS = ["llama3.1:8b", "mistral:7b"]
DEFAULT_MODEL = "llama3.1:8b"

# Hosted models, offered alongside the local ones only when a key is set,
# so the same prompts can be benchmarked against a hosted API.
ANTHROPIC_MODELS = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"]

ALLOWED_STEREOTYPES = [
    "designConstraint",
    "extendedRequirement",
    "functionalRequirement",
    "interfaceRequirement",
    "performanceRequirement",
    "physicalRequirement",
]

ALLOWED_VERIFY_METHODS = ["Analysis", "Demonstration", "Inspection", "Test"]

MAX_REPROMPTS = 3

# Chat repairs on the same budget as the Requirements tab. Measured on
# llama3.1:8b a chat repair is ~9s, so the worst case stays inside a turn
# a person will sit through, and one budget means one story to tell.
CHAT_MAX_REPROMPTS = MAX_REPROMPTS

# A response that is not parseable JSON is a different failure from one that
# breaks a writing rule: the content may be fine and only the envelope is
# wrong. Retried separately, and kept low because a model that ignores the
# format contract twice will usually ignore it a third time.
MAX_FORMAT_RETRIES = 2

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
STATE_FILE = os.environ.get("STATE_FILE", os.path.join(DATA_DIR, "state.json"))
