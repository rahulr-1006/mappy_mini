"""Settings, model lists, and the retry budgets."""

import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

AVAILABLE_MODELS = ["llama3.1:8b"]

DEFAULT_MODEL = "claude-haiku-4-5" if ANTHROPIC_API_KEY else AVAILABLE_MODELS[0]

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

CHAT_MAX_REPROMPTS = MAX_REPROMPTS

MAX_FORMAT_RETRIES = 2

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
