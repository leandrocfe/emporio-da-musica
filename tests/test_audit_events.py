"""Seam 2 + 4 — what the Assistant writes to the JSONL audit log with a scripted model."""

import json
import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest

from emporio.app import build_assistant
from emporio.audit_log import JsonlEventSink
from emporio.clock import STORE_TIMEZONE
from emporio.llm import LLMResponse, Message, TokenUsage
from emporio.prompt import PROMPT_VERSION
from emporio.session import Session

from .fakes import ScriptedLLM, asks, says, tool_call

NOW = datetime(2026, 3, 23, 10, 0, tzinfo=STORE_TIMEZONE)
ORDER_7_EMAIL = "leticia.rocha@jmail.com"
ORDER_7_PHONE = "67997890123"


def run(
    db_path: Path, tmp_path: Path, script: list[LLMResponse], message: str = "oi"
) -> tuple[list[dict[str, object]], str]:
    log = tmp_path / "logs" / "audit.jsonl"
    assistant = build_assistant(
        ScriptedLLM(script),
        db_path,
        events=JsonlEventSink(log, clock=lambda: NOW),
        clock=lambda: NOW,
    )
    assistant.reply(Session(id="s1"), message)
    text = log.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()], text


def test_a_tool_turn_is_logged_in_order_with_session_and_timestamp(
    db_path: Path, tmp_path: Path
) -> None:
    script = [
        asks(tool_call("c1", "search_products", {"query": "violao yamaha"})),
        says("Temos!"),
    ]

    lines, _ = run(db_path, tmp_path, script, "tem violão Yamaha?")

    assert [line["type"] for line in lines] == [
        "customer_message",
        "llm_call",
        "tool_call",
        "llm_call",
        "final_response",
    ]
    assert {line["session_id"] for line in lines} == {"s1"}
    assert {line["ts"] for line in lines} == {"2026-03-23T10:00:00-04:00"}
    assert lines[0]["content"] == "tem violão Yamaha?"
    assert lines[4]["content"] == "Temos!"
    tool = lines[2]
    assert tool["name"] == "search_products"
    assert tool["ok"] is True
    assert isinstance(tool["duration_ms"], int)
    assert json.loads(str(tool["arguments"])) == {"query": "violao yamaha"}


def test_product_names_in_results_are_not_masked(db_path: Path, tmp_path: Path) -> None:
    script = [asks(tool_call("c1", "search_products", {"query": "violao yamaha"})), says("ok")]

    lines, _ = run(db_path, tmp_path, script)

    result = lines[2]["result"]
    assert isinstance(result, dict)
    assert "Yamaha" in json.dumps(result, ensure_ascii=False)
    assert "***" not in json.dumps(result)


def test_llm_call_logs_model_latency_tokens_round_and_prompt_identity(
    db_path: Path, tmp_path: Path
) -> None:
    usage = TokenUsage(
        prompt_tokens=1200, completion_tokens=80, cache_read_tokens=1000, cache_creation_tokens=50
    )
    script = [
        LLMResponse(content="Oi!", usage=usage, model="claude-sonnet-5-5"),
    ]

    lines, text = run(db_path, tmp_path, script)

    call = lines[1]
    assert call["round"] == 1
    assert call["model"] == "claude-sonnet-5-5"
    assert isinstance(call["latency_ms"], int)
    assert call["prompt_tokens"] == 1200
    assert call["completion_tokens"] == 80
    assert call["total_tokens"] == 1280
    assert call["cache_read_tokens"] == 1000
    assert call["cache_creation_tokens"] == 50
    assert call["prompt_version"] == PROMPT_VERSION
    assert re.fullmatch(r"[0-9a-f]{12}", str(call["prompt_hash"]))
    assert "Você é a Lia" not in text  # the prompt itself is never logged
    assert "MANUAL DE POLÍTICAS" not in text


def test_the_prompt_hash_is_stable_across_turns(db_path: Path, tmp_path: Path) -> None:
    script = [asks(tool_call("c1", "search_products", {"query": "x"})), says("ok")]

    lines, _ = run(db_path, tmp_path, script)

    hashes = {line["prompt_hash"] for line in lines if line["type"] == "llm_call"}
    assert len(hashes) == 1


def test_get_order_contact_is_masked_in_arguments_and_customer_name_in_the_result(
    db_path: Path, tmp_path: Path
) -> None:
    script = [
        asks(tool_call("c1", "get_order", {"order_id": 7, "email_or_phone": ORDER_7_PHONE})),
        says("Pedido verificado"),
    ]

    lines, text = run(
        db_path, tmp_path, script, f"pedido 7, meu e-mail {ORDER_7_EMAIL} ou {ORDER_7_PHONE}"
    )

    assert ORDER_7_PHONE not in text
    assert ORDER_7_EMAIL not in text
    assert "7890123" not in text
    tool = lines[2]
    assert json.loads(str(tool["arguments"])) == {"order_id": 7, "email_or_phone": "*********23"}
    result = tool["result"]
    assert isinstance(result, dict)
    assert result["verified"] is True
    assert "Letícia" not in text
    assert lines[0]["content"] == "pedido 7, meu e-mail l***@j***.com ou *********23"


def test_register_complaint_masks_name_email_and_phone_in_arguments_and_description(
    db_path: Path, tmp_path: Path
) -> None:
    arguments = {
        "name": "Carlos Souza",
        "contact": "carlos@exemplo.com",
        "description": "Ligue para (67) 99111-2233 sobre o Pedido 7",
    }
    script = [asks(tool_call("c1", "register_complaint", arguments)), says("Protocolo gerado")]

    lines, text = run(db_path, tmp_path, script)

    assert "Carlos" not in text
    assert "carlos@exemplo.com" not in text
    assert "99111" not in text
    tool = lines[2]
    assert tool["name"] == "register_complaint"
    assert json.loads(str(tool["arguments"])) == {
        "name": "***",
        "contact": "c***@e***.com",
        "description": "Ligue para (**) *****-**33 sobre o Pedido 7",
    }
    result = tool["result"]
    assert isinstance(result, dict)
    assert str(result["protocol"]).startswith("EMP-20260323-")  # the Protocolo is not masked


def test_a_failed_tool_call_is_logged_with_ok_false(db_path: Path, tmp_path: Path) -> None:
    script = [asks(tool_call("c1", "nope", {})), says("ok")]

    lines, _ = run(db_path, tmp_path, script)

    assert lines[2]["ok"] is False
    result = lines[2]["result"]
    assert isinstance(result, dict)
    assert isinstance(result["error"], dict)
    assert result["error"]["code"] == "unknown_tool"


class ProviderDownError(Exception):
    pass


class DownLLM:
    def complete(
        self, messages: Sequence[Message], tools: Sequence[dict[str, object]]
    ) -> LLMResponse:
        raise ProviderDownError("timeout falando com joao@gmail.com")


def test_a_failed_turn_logs_an_error_event_and_still_raises(db_path: Path, tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    assistant = build_assistant(
        DownLLM(), db_path, events=JsonlEventSink(log, clock=lambda: NOW), clock=lambda: NOW
    )

    with pytest.raises(ProviderDownError):
        assistant.reply(Session(id="s1"), "oi")

    lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [line["type"] for line in lines] == ["customer_message", "error"]
    assert lines[1]["error_type"] == "ProviderDownError"
    assert lines[1]["message"] == "timeout falando com j***@g***.com"


def test_get_product_name_argument_is_not_a_customer_name(db_path: Path, tmp_path: Path) -> None:
    script = [asks(tool_call("c1", "get_product", {"product_id": 3})), says("ok")]

    lines, _ = run(db_path, tmp_path, script)

    assert json.loads(str(lines[2]["arguments"])) == {"product_id": 3}


def test_the_customer_first_name_in_the_final_response_is_logged_as_is(
    db_path: Path, tmp_path: Path
) -> None:
    # Documented limitation: Lia's own answers carry the first name of the verified
    # Customer (and the name given in a Reclamação); only tool data is masked.
    script = [
        asks(tool_call("c1", "get_order", {"order_id": 7, "email_or_phone": ORDER_7_PHONE})),
        says("Olá, Letícia! Seu pedido 7 está a caminho."),
    ]

    lines, _ = run(db_path, tmp_path, script, "pedido 7")

    assert lines[4]["content"] == "Olá, Letícia! Seu pedido 7 está a caminho."
    result = lines[2]["result"]
    assert isinstance(result, dict)
    assert "Letícia" not in json.dumps(result, ensure_ascii=False)


def test_get_order_with_the_phone_as_a_json_number_is_verified_and_masked(
    db_path: Path, tmp_path: Path
) -> None:
    script = [
        asks(tool_call("c1", "get_order", '{"order_id": 7, "email_or_phone": 67997890123}')),
        says("ok"),
    ]

    lines, text = run(db_path, tmp_path, script, "pedido 7")

    assert ORDER_7_PHONE not in text
    assert "7890123" not in text
    tool = lines[2]
    assert json.loads(str(tool["arguments"])) == {"order_id": 7, "email_or_phone": "*********23"}
    result = tool["result"]
    assert isinstance(result, dict)
    assert result["verified"] is True


def test_register_complaint_with_the_contact_as_a_json_number_is_masked(
    db_path: Path, tmp_path: Path
) -> None:
    arguments = '{"name": "Carlos", "contact": 67997890123, "description": "d"}'
    script = [asks(tool_call("c1", "register_complaint", arguments)), says("ok")]

    lines, text = run(db_path, tmp_path, script)

    assert "7890123" not in text
    assert "Carlos" not in text
    assert json.loads(str(lines[2]["arguments"]))["contact"] == "*********23"


def test_the_real_prompt_hash_and_model_are_logged_unmasked(db_path: Path, tmp_path: Path) -> None:
    lines, _ = run(db_path, tmp_path, [says("ok")])

    llm = lines[1]
    assert re.fullmatch(r"[0-9a-f]{12}", str(llm["prompt_hash"]))
    assert "*" not in str(llm["prompt_hash"])
    assert llm["prompt_version"] == PROMPT_VERSION
