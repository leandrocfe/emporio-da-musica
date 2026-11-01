"""Composition root: the production Assistant answers from the real catalog."""

from pathlib import Path

from emporio.app import build_assistant
from emporio.session import Session

from .fakes import ScriptedLLM, asks, says, tool_call


def test_assembled_assistant_searches_the_seeded_catalog(db_path: Path) -> None:
    llm = ScriptedLLM(
        [asks(tool_call("call_1", "search_products", {"query": "violao yamaha"})), says("Temos!")]
    )

    answer = build_assistant(llm=llm, db_path=db_path).reply(Session(id="s1"), "tem violão Yamaha?")

    assert answer == "Temos!"
    result = llm.tool_results(1)["call_1"]
    assert isinstance(result, dict)
    assert result["total"] == 7
