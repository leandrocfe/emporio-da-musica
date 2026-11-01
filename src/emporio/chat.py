"""Chainlit UI: a thin adapter over the Assistant.

It runs mounted at `/lia` by `emporio.web` (`uvicorn emporio.web:app`); standalone
`chainlit run src/emporio/chat.py` still starts the chat standalone, but the logo and
avatar URLs in `.chainlit/config.toml` are prefixed with `/lia`, so they only resolve mounted.

One Session per browser tab, in memory (ends on reload). Tool calls are never
shown to the Customer: no Chainlit steps are created for them; auditing goes
to the EventSink (the JSONL audit log).
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
from emporio.store_info import STORE_PHONE

AUTHOR = "Lia"
WELCOME = (
    "## Olá, eu sou a Lia.\n\n"
    "Que bom ter você na Empório da Música. Como posso ajudar?\n\n"
    "Escolha um assunto ou escreva sua mensagem abaixo."
)
SHORTCUTS = {
    "Procurar instrumento": "Quero procurar um instrumento.",
    "Status do pedido": "Quero consultar o status do meu pedido.",
    "Trocas e devoluções": "Quero saber sobre trocas e devoluções.",
    "Horário e endereço": "Qual é o horário de funcionamento e o endereço da loja?",
}
LOADING = "![](/lia/public/lia-pensando.svg) Lia está pensando…"
FRIENDLY_ERROR = (
    "Ops, tive um problema técnico para responder agora. Pode tentar de novo em instantes? "
    f"Se preferir, fale com a loja pelo telefone {STORE_PHONE}."
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
    actions = [
        cl.Action(
            name="shortcut", label=label, payload={"label": label}, id=f"lia-shortcut-{uuid4()}"
        )
        for label in SHORTCUTS
    ]
    await cl.Message(content=WELCOME, author=AUTHOR, actions=actions).send()  # type: ignore[no-untyped-call]
    # Warm-up off the event loop: the first build imports litellm (seconds of CPU).
    # A failure here is retried and reported on the first message.
    try:
        await cl.make_async(_assistant)()
    except Exception:
        logger.exception("assistant warm-up failed (session %s)", _current_session().id)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    session = _current_session()
    response = cl.Message(content=LOADING, author=AUTHOR)
    await response.send()  # type: ignore[no-untyped-call]
    try:
        assistant = await cl.make_async(_assistant)()  # cached; built off the event loop
        answer = await cl.make_async(assistant.reply)(session, message.content)
    except Exception as exc:
        # Only the exception type and the session id reach stderr/docker logs: the
        # message may echo Customer data. The full, masked error event is already in
        # the JSONL audit log (emitted by the Assistant).
        logger.error("assistant reply failed (session %s): %s", session.id, type(exc).__name__)
        answer = FRIENDLY_ERROR
    response.content = answer
    # Chainlit leaves Message.send and Message.update unannotated.
    await response.update()  # type: ignore[no-untyped-call]


@cl.action_callback("shortcut")
async def on_shortcut(action: cl.Action) -> None:
    label = action.payload.get("label")
    if not isinstance(label, str) or label not in SHORTCUTS:
        return
    message = cl.Message(content=SHORTCUTS[label], author="Cliente", type="user_message")
    await message.send()  # type: ignore[no-untyped-call]
    await on_message(message)
