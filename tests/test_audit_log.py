"""Seam 4 — the JSONL audit log sink (ADR-0001 EventSink, ADR-0004)."""

import json
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from emporio.audit_log import JsonlEventSink, log_path_from_env
from emporio.events import Event

NOW = datetime(2026, 3, 23, 10, 0, tzinfo=ZoneInfo("America/Campo_Grande"))


def read_lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_each_event_is_one_json_line_with_timestamp_session_and_type(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "audit.jsonl"  # the directory is created on demand
    sink = JsonlEventSink(path, clock=lambda: NOW)

    sink.emit(Event("customer_message", "s1", {"content": "Olá, violão é bom? ção"}))
    sink.emit(Event("final_response", "s1", {"content": "Sim!"}))

    assert read_lines(path) == [
        {
            "ts": "2026-03-23T10:00:00-04:00",
            "session_id": "s1",
            "type": "customer_message",
            "content": "Olá, violão é bom? ção",
        },
        {
            "ts": "2026-03-23T10:00:00-04:00",
            "session_id": "s1",
            "type": "final_response",
            "content": "Sim!",
        },
    ]
    assert "ção" in path.read_text(encoding="utf-8")  # real UTF-8, not \u escapes


def test_personal_data_is_masked_before_it_is_written(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlEventSink(path, clock=lambda: NOW)

    sink.emit(
        Event(
            "customer_message",
            "s1",
            {"content": "meu e-mail é joao@gmail.com, tel +55 (67) 99789-0123"},
        )
    )

    text = path.read_text(encoding="utf-8")
    assert "joao@gmail.com" not in text
    assert "99789" not in text
    assert "j***@g***.com" in text


def test_large_results_are_truncated_after_masking(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlEventSink(path, clock=lambda: NOW, max_result_chars=60)
    result = {"items": [{"id": n, "owner": "joao@gmail.com"} for n in range(50)]}

    sink.emit(Event("tool_call", "s1", {"name": "t", "ok": True, "result": result}))
    sink.emit(Event("tool_call", "s1", {"name": "t", "ok": True, "result": {"total": 0}}))

    big, small = read_lines(path)
    summary = big["result"]
    assert isinstance(summary, dict)
    assert summary["truncated"] is True
    assert isinstance(summary["chars"], int)
    assert summary["chars"] > 60
    preview = summary["preview"]
    assert isinstance(preview, str)
    assert len(preview) == 60
    assert "joao" not in preview
    assert small["result"] == {"total": 0}


def test_concurrent_writers_never_interleave_lines(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlEventSink(path, clock=lambda: NOW)
    padding = "x" * 5000

    def write(thread_id: int) -> None:
        for n in range(25):
            sink.emit(Event("customer_message", f"s{thread_id}", {"content": padding, "n": n}))

    threads = [threading.Thread(target=write, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    lines = read_lines(path)  # every line parses
    assert len(lines) == 8 * 25


def test_a_failing_write_does_not_raise_and_is_reported_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x")
    sink = JsonlEventSink(blocker / "audit.jsonl", clock=lambda: NOW)

    sink.emit(Event("customer_message", "s1", {"content": "oi joao@gmail.com"}))
    sink.emit(Event("customer_message", "s1", {"content": "oi"}))

    err = capsys.readouterr().err
    assert err.count("audit log") == 1
    assert "joao@gmail.com" not in err


def test_the_sink_recovers_when_the_path_becomes_writable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "dir"
    blocker.write_text("x")
    sink = JsonlEventSink(blocker / "audit.jsonl", clock=lambda: NOW)
    sink.emit(Event("customer_message", "s1", {"content": "perdido"}))
    blocker.unlink()

    sink.emit(Event("customer_message", "s1", {"content": "gravado"}))

    assert [line["content"] for line in read_lines(tmp_path / "dir" / "audit.jsonl")] == ["gravado"]
    assert capsys.readouterr().err.count("audit log") == 1


def test_log_path_comes_from_log_path_then_log_dir_then_default() -> None:
    assert log_path_from_env({"LOG_PATH": "/x/a.jsonl", "LOG_DIR": "/y"}) == Path("/x/a.jsonl")
    assert log_path_from_env({"LOG_DIR": "/y"}) == Path("/y/audit.jsonl")
    assert log_path_from_env({}) == Path("logs/audit.jsonl")
    assert log_path_from_env({"LOG_PATH": " ", "LOG_DIR": ""}) == Path("logs/audit.jsonl")


def test_a_lone_surrogate_in_the_message_does_not_break_the_log(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlEventSink(path, clock=lambda: NOW)

    sink.emit(Event("customer_message", "s1", {"content": "oi \ud83d joao@gmail.com"}))
    sink.emit(Event("customer_message", "s1", {"content": "depois"}))

    lines = read_lines(path)
    assert [line["content"] for line in lines][1] == "depois"
    assert "j***@g***.com" in str(lines[0]["content"])


def test_values_json_cannot_serialize_are_logged_as_text(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlEventSink(path, clock=lambda: NOW)

    sink.emit(Event("tool_call", "s1", {"name": "t", "result": {"when": NOW, "o": object}}))

    (line,) = read_lines(path)
    result = line["result"]
    assert isinstance(result, dict)
    assert str(result["when"]).startswith("2026-03-23")


class Unprintable:
    def __str__(self) -> str:
        raise TypeError("cannot render joao@gmail.com")


def test_a_serialization_error_is_reported_not_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlEventSink(path, clock=lambda: NOW)

    sink.emit(Event("tool_call", "s1", {"name": "t", "result": Unprintable()}))
    sink.emit(Event("customer_message", "s1", {"content": "ok"}))

    err = capsys.readouterr().err
    assert err.count("audit log") == 1
    assert "joao" not in err
    assert [line["content"] for line in read_lines(path)] == ["ok"]


def test_a_structure_too_deep_to_mask_is_logged_with_a_marker(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlEventSink(path, clock=lambda: NOW)
    deep: object = "joao@gmail.com"
    for _ in range(5000):
        deep = [deep]

    sink.emit(Event("tool_call", "s1", {"name": "t", "result": deep, "ok": True}))

    (line,) = read_lines(path)
    assert line["result"] == "[not logged: nested too deeply]"
    assert line["ok"] is True


def test_the_envelope_wins_over_event_fields(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlEventSink(path, clock=lambda: NOW)

    sink.emit(
        Event("customer_message", "real", {"ts": "FAKE", "session_id": "FAKE", "type": "FAKE"})
    )

    (line,) = read_lines(path)
    assert (line["ts"], line["session_id"], line["type"]) == (
        "2026-03-23T10:00:00-04:00",
        "real",
        "customer_message",
    )


def test_the_warning_returns_on_a_new_failure_after_a_successful_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "logs"
    sink = JsonlEventSink(folder / "audit.jsonl", clock=lambda: NOW)
    folder.write_text("x")  # not a directory: fails
    sink.emit(Event("customer_message", "s1", {"content": "1"}))
    folder.unlink()
    sink.emit(Event("customer_message", "s1", {"content": "2"}))  # works again
    (folder / "audit.jsonl").unlink()
    folder.rmdir()
    folder.write_text("x")  # fails a second time
    sink.emit(Event("customer_message", "s1", {"content": "3"}))

    assert capsys.readouterr().err.count("audit log") == 2


def test_very_long_text_is_clipped_after_masking(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlEventSink(path, clock=lambda: NOW, max_text_chars=100)

    sink.emit(Event("customer_message", "s1", {"content": "joao@gmail.com " + "a" * 500}))
    sink.emit(Event("customer_message", "s1", {"content": "curta"}))

    long, short = read_lines(path)
    content = str(long["content"])
    assert content.startswith("j***@g***.com ")
    assert content.endswith("[truncated, 514 chars]")
    assert len(content) < 150
    assert short["content"] == "curta"


def test_json_text_too_deep_to_parse_is_still_logged_masked_and_clipped(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    sink = JsonlEventSink(path, clock=lambda: NOW, max_text_chars=100)
    deep = "[" * 100_000 + '"joao@gmail.com"' + "]" * 100_000

    sink.emit(Event("customer_message", "s1", {"content": deep}))

    (line,) = read_lines(path)
    content = str(line["content"])
    assert content.endswith(f"[truncated, {len(deep) - 1} chars]")
    assert "joao@gmail.com" not in path.read_text(encoding="utf-8")
