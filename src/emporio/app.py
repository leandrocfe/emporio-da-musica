"""Composition root: wires the Assistant's ports to their production adapters.

Kept free of Chainlit so any UI (or a future HTTP API) builds the same Assistant.
"""

from pathlib import Path

from emporio.assistant import Assistant
from emporio.db import db_path_from_env
from emporio.events import EventSink
from emporio.llm import LLMClient
from emporio.store import StoreService
from emporio.store_tools import register_store_tools
from emporio.tools import ToolRegistry


def build_assistant(llm: LLMClient, db_path: Path, events: EventSink | None = None) -> Assistant:
    registry = ToolRegistry()
    register_store_tools(registry, StoreService(db_path))
    return Assistant(llm, registry, events=events)


def build_assistant_from_env() -> Assistant:
    """Production wiring: LiteLLM (`LLM_MODEL`) over the database at `DB_PATH`."""
    # Imported here: litellm is slow to import and only production needs it.
    from emporio.litellm_client import LiteLLMClient

    return build_assistant(llm=LiteLLMClient.from_env(), db_path=db_path_from_env())
