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

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
STATE_FILE = os.environ.get("STATE_FILE", os.path.join(DATA_DIR, "state.json"))
