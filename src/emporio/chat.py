"""Chainlit UI: a thin adapter over the Assistant (`chainlit run src/emporio/chat.py`).

One Session per browser tab, in memory (ends on reload). Tool calls are never
shown to the Customer: no Chainlit steps are created for them; auditing goes
to the EventSink (ticket 08).
"""

import logging
import os
from functools import cache
from uuid import uuid4

import chainlit as cl
from chainlit.user_session import SessionAccessor

from emporio.app import build_assistant_from_env
from emporio.assistant import Assistant
from emporio.clock import clock_from_env
from emporio.session import Session

AUTHOR = "Lia"
FRIENDLY_ERROR = (
    "Ops, tive um problema técnico para responder agora. Pode tentar de novo em instantes? "
    "Se preferir, fale com a loja pelo telefone (67) 3341-4444."
)

logger = logging.getLogger(__name__)

# Fail fast: an invalid AGENT_NOW stops the app at startup instead of showing the
# Customer a generic error on every message (the warm-up below swallows exceptions).
clock_from_env(os.environ)

_session: SessionAccessor[Session | None] = cl.user_session.create_accessor("lia_session", None)


@cache
def _assistant() -> Assistant:
    return build_assistant_from_env()


def _current_session() -> Session:
    session = _session.get()
    if session is None:
        session = Session(id=str(uuid4()))
        _session.set(session)
    return session


@cl.on_chat_start
async def start() -> None:
    _session.set(Session(id=str(uuid4())))
    # Warm-up off the event loop: the first build imports litellm (seconds of CPU).
    # A failure here is retried and reported on the first message.
    try:
        await cl.make_async(_assistant)()
    except Exception:
        logger.exception("assistant warm-up failed (session %s)", _current_session().id)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    session = _current_session()
    try:
        assistant = await cl.make_async(_assistant)()  # cached; built off the event loop
        answer = await cl.make_async(assistant.reply)(session, message.content)
    except Exception:
        # Traceback only (no message history, no credentials); the masked JSONL
        # audit log with the error event is ticket 08/09.
        logger.exception("assistant reply failed (session %s)", session.id)
        answer = FRIENDLY_ERROR
    # Chainlit leaves `Message.send` unannotated.
    await cl.Message(content=answer, author=AUTHOR).send()  # type: ignore[no-untyped-call]
