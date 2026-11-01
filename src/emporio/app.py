"""Composition root: wires the Assistant's ports to their production adapters.

Kept free of Chainlit so any UI (or a future HTTP API) builds the same Assistant.
"""

import os
from pathlib import Path

from emporio.assistant import Assistant
from emporio.audit_log import JsonlEventSink, log_path_from_env
from emporio.clock import Clock, clock_from_env, real_clock
from emporio.complaint_tools import register_complaint_tools
from emporio.complaints import ComplaintService
from emporio.db import db_path_from_env
from emporio.events import EventSink
from emporio.llm import LLMClient
from emporio.store import StoreService
from emporio.store_tools import register_store_tools
from emporio.tools import ToolRegistry


def build_assistant(
    llm: LLMClient,
    db_path: Path,
    events: EventSink | None = None,
    clock: Clock = real_clock,
) -> Assistant:
    store = StoreService(db_path)
    registry = ToolRegistry()
    register_store_tools(registry, store)
    register_complaint_tools(registry, ComplaintService(db_path))
    return Assistant(llm, registry, events=events, clock=clock, categories=store.category_names())


def build_assistant_from_env() -> Assistant:
    """Production wiring: LiteLLM (`LLM_MODEL`) over the database at `DB_PATH`.

    Events go to the masked JSONL audit log (`LOG_PATH`, or `LOG_DIR`/audit.jsonl).
    """
    # Imported here: litellm is slow to import and only production needs it.
    from emporio.litellm_client import LiteLLMClient

    clock = clock_from_env(os.environ)  # invalid AGENT_NOW fails here, with a clear message
    return build_assistant(
        llm=LiteLLMClient.from_env(),
        db_path=db_path_from_env(),
        events=JsonlEventSink(log_path_from_env(os.environ), clock=clock),
        clock=clock,
    )
