"""Seam 5 — the example-conversation generator, with a scripted model and no network."""

from datetime import datetime
from pathlib import Path

import pytest

from emporio.clock import STORE_TIMEZONE
from emporio.examples import (
    SCRIPTS,
    ConversationScript,
    ExampleGenerationError,
    generate_all,
    generate_conversation,
)
from emporio.llm import LLMResponse

from .conftest import DATA_DIR
from .fakes import ScriptedLLM, asks, says, tool_call

NOW = datetime(2026, 3, 23, 10, 0, tzinfo=STORE_TIMEZONE)
EMAIL = "leticia.rocha@jmail.com"

ORDER_SCRIPT = ConversationScript(
    slug="devolucao",
    title="Devolução de um Pedido",
    summary="Cliente pede devolução.",
    turns=("Quero devolver o Pedido 7.", f"Meu e-mail é {EMAIL}"),
)


def order_conversation_llm() -> ScriptedLLM:
    return ScriptedLLM(
        [
            says("Qual o e-mail do cadastro?"),
            asks(tool_call("c1", "get_order", {"order_id": 7, "email_or_phone": EMAIL})),
            says("Encontrei o Pedido 7, Letícia."),
        ]
    )


def test_markdown_has_title_turns_and_masked_log_excerpt(tmp_path: Path) -> None:
    markdown = generate_conversation(
        ORDER_SCRIPT, order_conversation_llm(), DATA_DIR, NOW, work_dir=tmp_path
    )

    assert markdown.startswith("# Devolução de um Pedido\n")
    assert "## Conversa" in markdown
    assert "**Cliente:** Quero devolver o Pedido 7." in markdown
    assert "**Lia:** Qual o e-mail do cadastro?" in markdown
    assert "## Log de auditoria" in markdown
    assert "### Turno 2" in markdown
    assert '"name": "get_order"' in markdown
    assert "order_id" in markdown
    assert "2026-03-23T10:00:00-04:00" in markdown


def test_personal_data_is_masked_in_the_whole_document(tmp_path: Path) -> None:
    markdown = generate_conversation(
        ORDER_SCRIPT, order_conversation_llm(), DATA_DIR, NOW, work_dir=tmp_path
    )

    assert EMAIL not in markdown
    assert "leticia.rocha" not in markdown


def test_each_conversation_has_a_fresh_session_and_only_its_own_log(tmp_path: Path) -> None:
    first = generate_conversation(
        ORDER_SCRIPT, order_conversation_llm(), DATA_DIR, NOW, work_dir=tmp_path
    )
    other = ConversationScript(slug="x", title="Outra", summary="s", turns=("Oi",))
    second = generate_conversation(other, ScriptedLLM([says("Olá!")]), DATA_DIR, NOW, tmp_path)

    assert "get_order" in first
    assert "get_order" not in second
    assert "### Turno 2" not in second


def test_generate_all_writes_one_file_per_script_plus_an_index(tmp_path: Path) -> None:
    llm = ScriptedLLM([says("Resposta.") for _ in range(sum(len(s.turns) for s in SCRIPTS))])
    out = tmp_path / "conversas"

    written = generate_all(llm, out, DATA_DIR, NOW)

    assert len(SCRIPTS) == 5
    assert [path.name for path in written] == [f"{s.slug}.md" for s in SCRIPTS]
    assert all(path.parent == out and path.read_text("utf-8") for path in written)
    index = (out / "README.md").read_text("utf-8")
    assert all(script.title in index and f"{script.slug}.md" in index for script in SCRIPTS)


def test_scripts_cover_the_five_scenarios_in_natural_portuguese() -> None:
    joined = " ".join(turn for script in SCRIPTS for turn in script.turns).lower()

    for expected in ("1000", "gf-3d", "takamine gd20", "pedido 7", EMAIL, "reclam"):
        assert expected in joined
    assert [s.slug for s in SCRIPTS] == [
        "01-violoes-ate-mil-reais",
        "02-takamine-gd20-promocao-expirada",
        "03-devolucao-pedido-7",
        "04-acessorios-e-fora-de-escopo",
        "05-reclamacao-com-protocolo",
    ]


class FailingLLM:
    def complete(self, messages: object, tools: object) -> LLMResponse:
        raise ConnectionError("sem chave")


def test_provider_failure_aborts_without_writing_files(tmp_path: Path) -> None:
    out = tmp_path / "conversas"

    with pytest.raises(ExampleGenerationError):
        generate_all(FailingLLM(), out, DATA_DIR, NOW, scripts=(ORDER_SCRIPT,))

    assert not out.exists()


def test_round_limit_fallback_aborts_the_run(tmp_path: Path) -> None:
    calls = [asks(tool_call(f"c{i}", "get_product", {"name": "x"})) for i in range(5)]

    with pytest.raises(ExampleGenerationError):
        generate_conversation(
            ConversationScript("x", "T", "s", ("Oi",)),
            ScriptedLLM(calls),
            DATA_DIR,
            NOW,
            work_dir=tmp_path,
        )


def test_empty_answer_fallback_aborts_the_run(tmp_path: Path) -> None:
    with pytest.raises(ExampleGenerationError):
        generate_conversation(
            ConversationScript("x", "T", "s", ("Oi",)),
            ScriptedLLM([LLMResponse(content=None)]),
            DATA_DIR,
            NOW,
            work_dir=tmp_path,
        )
