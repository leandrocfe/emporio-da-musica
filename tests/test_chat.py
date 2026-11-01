"""Behavior at the Chainlit adapter boundary, without network or API keys."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from xml.etree import ElementTree

import chainlit as cl
import pytest

from emporio import chat
from emporio.session import Session


@pytest.mark.parametrize(
    ("label", "message"),
    [
        ("Procurar instrumento", "Quero procurar um instrumento."),
        ("Status do pedido", "Quero consultar o status do meu pedido."),
        ("Trocas e devoluções", "Quero saber sobre trocas e devoluções."),
        ("Horário e endereço", "Qual é o horário de funcionamento e o endereço da loja?"),
    ],
)
def test_shortcut_sends_customer_message_to_assistant(
    monkeypatch: pytest.MonkeyPatch, label: str, message: str
) -> None:
    sent = MagicMock()
    sent.send = AsyncMock()
    factory = MagicMock(return_value=sent)
    handler = AsyncMock()
    monkeypatch.setattr(cl, "Message", factory)
    monkeypatch.setattr(chat, "on_message", handler)

    asyncio.run(chat.on_shortcut(cl.Action(name="shortcut", payload={"label": label})))

    factory.assert_called_once_with(content=message, author="Cliente", type="user_message")
    sent.send.assert_awaited_once()
    handler.assert_awaited_once_with(sent)


def test_response_replaces_loading_with_friendly_error(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock()
    response.send = AsyncMock()
    response.update = AsyncMock()
    factory = MagicMock(return_value=response)
    monkeypatch.setattr(cl, "Message", factory)
    monkeypatch.setattr(chat, "_current_session", lambda: Session(id="test"))

    def fail() -> None:
        raise RuntimeError("private provider details")

    monkeypatch.setattr(chat, "_assistant", fail)

    async def run() -> None:
        await chat.on_message(MagicMock(content="Olá"))

    asyncio.run(run())

    factory.assert_called_once_with(content=chat.LOADING, author="Lia")
    response.send.assert_awaited_once()
    response.update.assert_awaited_once()
    assert response.content == chat.FRIENDLY_ERROR


def test_welcome_actions_have_stable_styling_hook_and_unique_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = MagicMock()
    sent.send = AsyncMock()
    factory = MagicMock(return_value=sent)
    monkeypatch.setattr(cl, "Message", factory)
    monkeypatch.setattr(chat, "_session", MagicMock())
    monkeypatch.setattr(chat, "_assistant", lambda: None)

    asyncio.run(chat.start())

    actions = factory.call_args.kwargs["actions"]
    assert [action.label for action in actions] == list(chat.SHORTCUTS)
    assert all(action.id.startswith("lia-shortcut-") for action in actions)
    assert len({action.id for action in actions}) == len(actions)
    sent.send.assert_awaited_once()


def test_loading_svg_is_accessible_and_respects_reduced_motion() -> None:
    svg = Path(__file__).parent.parent / "public" / "lia-pensando.svg"
    root = ElementTree.parse(svg).getroot()  # noqa: S314 (repo-owned file)

    assert root.find("{http://www.w3.org/2000/svg}title") is not None
    assert root.get("role") == "img"
    assert "prefers-reduced-motion" in svg.read_text(encoding="utf-8")
    assert "/lia/public/lia-pensando.svg" in chat.LOADING
