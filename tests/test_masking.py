"""Seam 3 — masking of personal data before anything reaches the audit log (ADR-0004)."""

import hashlib
import json
import time

import pytest

from emporio.masking import mask_event_data, mask_value


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("joao@gmail.com", "j***@g***.com"),
        ("maria.silva+loja@mail.example.com.br", "m***@m***.example.com.br"),
        ("x@y.io", "x***@y***.io"),
    ],
)
def test_emails_keep_first_letters_and_the_domain_suffix(raw: str, masked: str) -> None:
    assert mask_value(raw) == masked
    assert mask_value(f"meu e-mail é {raw}, obrigado") == f"meu e-mail é {masked}, obrigado"


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("+55 (67) 99789-0123", "+** (**) *****-**23"),
        ("(67) 99789-0123", "(**) *****-**23"),
        ("67997890123", "*********23"),
        ("997890123", "*******23"),
        ("99789-0123", "*****-**23"),
        ("3341-4445", "****-**45"),
        ("(67) 3341-4445", "(**) ****-**45"),
        ("067997890123", "**********23"),
        ("99789\u20130123", "*****\u2013**23"),
        ("99789 - 0123", "*****_-_**23".replace("_", " ")),
    ],
)
def test_phones_keep_only_the_last_two_digits(raw: str, masked: str) -> None:
    assert mask_value(raw) == masked
    assert mask_value(f"liga em {raw}.") == f"liga em {masked}."


def test_a_phone_after_a_dash_or_glued_to_letters_is_masked() -> None:
    assert mask_value("tel -99789-0123") == "tel -*****-**23"
    assert mask_value("-99789-0123") == "-*****-**23"
    assert mask_value("fone99789-0123") == "fone*****-**23"


def test_the_stores_own_public_phone_is_kept() -> None:
    text = "Fale com a loja: (67) 3341-4444 ou 3341-4444."

    assert mask_value(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "Pedido 12 do produto 7",
        "preço 549.00 e 3450.00 (a vista 3277.50)",
        "R$ 3.450,00 em 10x",
        "protocolo EMP-20260323-K7XMQ2 registrado",
        "data 2026-03-23 e 23/03/2026",
        "2026-03-23T10:00:00-04:00",
        "2026-03-23T10:00:00.123456-04:00",
        "sha256 3f2a9c81d4e7",
        "550e8400-e29b-41d4-a716-446655440000",
        "latency 1523 ms, 12000 tokens",
        "ratio 0.12345678 e 12345678.50",
        "rastreio BRKR1122334BR e BRQM7890123BR",
        "EMP-20260323-K7XMQ2 e EMP-20261231-23456Z",
        "Protocolo:EMP-20260323-K7XMQ2.",
        "claude-sonnet-4-5-20250929",
    ],
)
def test_non_personal_numbers_are_left_alone(text: str) -> None:
    assert mask_value(text) == text


def test_non_string_scalars_pass_through() -> None:
    assert mask_value(42) == 42
    assert mask_value(549.0) == 549.0
    assert mask_value(True) is True
    assert mask_value(None) is None


def test_masking_recurses_through_dicts_lists_and_tuples() -> None:
    value = {"a": ["joao@gmail.com", ("(67) 99789-0123", 3)], "b": {"c": "ok"}}

    assert mask_value(value) == {
        "a": ["j***@g***.com", ["(**) *****-**23", 3]],
        "b": {"c": "ok"},
    }


def test_json_serialized_in_a_string_is_masked_textually() -> None:
    raw = json.dumps({"contact": "joao@gmail.com", "note": "ligue 99789-0123", "total": "549.00"})

    masked = mask_value(raw)

    assert isinstance(masked, str)
    assert json.loads(masked) == {
        "contact": "j***@g***.com",
        "note": "ligue *****-**23",
        "total": "549.00",
    }


@pytest.mark.parametrize("key", ["email_or_phone", "contact", "email", "phone"])
def test_contact_keys_are_masked_whatever_the_content(key: str) -> None:
    assert mask_value({key: "joao@gmail.com"}) == {key: "j***@g***.com"}
    assert mask_value({key: "zap do joao"}) == {key: "***"}


def test_customer_first_name_is_masked_by_key() -> None:
    assert mask_value({"order": {"customer_first_name": "Carlos", "id": 1}}) == {
        "order": {"customer_first_name": "***", "id": 1}
    }


def test_key_masking_also_works_inside_json_text_with_odd_contact() -> None:
    masked = mask_value('{"email_or_phone": "zap do joao", "order_id": 5}')

    assert masked == '{"email_or_phone": "***", "order_id": 5}'


def test_name_is_a_product_name_unless_the_tool_registers_a_complaint() -> None:
    product = {"name": "Violão Yamaha C40", "id": 3}
    assert mask_value(product) == product

    args = json.dumps({"name": "Carlos Souza", "contact": "carlos@x.com", "description": "d"})
    data = {"name": "register_complaint", "arguments": args, "result": {"protocol": "EMP-1-A"}}

    masked = mask_event_data("tool_call", data)

    assert masked["name"] == "register_complaint"  # the tool name is not a person
    assert isinstance(masked["arguments"], str)
    assert json.loads(masked["arguments"]) == {
        "name": "***",
        "contact": "c***@x***.com",
        "description": "d",
    }


def test_product_names_in_other_tool_calls_survive() -> None:
    data = {"name": "get_product", "arguments": '{"product_id": 3}', "result": {"name": "Violão"}}

    assert mask_event_data("tool_call", data) == data


def test_masking_is_idempotent() -> None:
    once = mask_value("joao@gmail.com e +55 (67) 99789-0123")

    assert mask_value(once) == once


@pytest.mark.parametrize("separator", ["\n", "\t", "\r", " "])
def test_phone_after_an_escaped_control_character_in_json_arguments_is_masked(
    separator: str,
) -> None:
    arguments = json.dumps({"description": f"Retorno:{separator}67997890123", "n": "99789-0123"})

    masked = mask_value(arguments)

    assert isinstance(masked, str)
    assert "7890123" not in masked
    assert "99789" not in masked
    assert json.loads(masked)["description"].endswith("*********23")


def test_phone_after_a_literal_backslash_escape_is_masked_even_in_broken_json() -> None:
    assert mask_value('{"d": "Retorno:\\n67997890123') == '{"d": "Retorno:\\n*********23'
    assert mask_value('{"d": "tel\\t997890123') == '{"d": "tel\\t*******23'


def test_escaped_unicode_email_in_json_text_is_masked_and_the_json_stays_valid() -> None:
    raw = json.dumps({"description": "email joão@x.com"})  # ensure_ascii: jo\u00e3o

    masked = mask_value(raw)

    assert isinstance(masked, str)
    assert json.loads(masked) == {"description": "email j***@x***.com"}


def test_accented_emails_are_masked() -> None:
    assert mask_value("joão@gmail.com") == "j***@g***.com"
    assert mask_value("joao@gmaíl.com") == "j***@g***.com"


def test_long_text_without_spaces_is_masked_in_linear_time() -> None:
    started = time.perf_counter()
    mask_value("a" * 100_000)
    mask_value("a." * 50_000)
    mask_value("1" * 100_000)

    assert time.perf_counter() - started < 0.5


# --- Personal data under a key, whatever its JSON type -------------------------------


@pytest.mark.parametrize("key", ["email_or_phone", "contact", "email", "phone"])
def test_a_phone_sent_as_a_json_number_under_a_contact_key_is_masked(key: str) -> None:
    assert mask_value({key: 67997890123}) == {key: "*********23"}
    assert mask_value(json.dumps({key: 67997890123})) == json.dumps({key: "*********23"})
    assert mask_value({key: 67997890123.0}) == {key: "***"}
    assert mask_value({key: 5}) == {key: "***"}


def test_containers_under_a_contact_key_are_masked_leaf_by_leaf() -> None:
    value = {"contact": [67997890123, "zap do joao", {"x": "joao@gmail.com", "y": None}]}

    assert mask_value(value) == {
        "contact": ["*********23", "***", {"x": "j***@g***.com", "y": None}]
    }


def test_none_and_booleans_under_a_contact_key_are_not_personal_data() -> None:
    assert mask_value({"contact": None, "email": True, "phone": False}) == {
        "contact": None,
        "email": True,
        "phone": False,
    }


def test_names_under_a_name_key_are_masked_whatever_their_type() -> None:
    value = {"customer_first_name": ["Carlos", 7, {"a": "Souza"}, None]}

    assert mask_value(value) == {"customer_first_name": ["***", "***", {"a": "***"}, None]}


def test_an_unquoted_number_under_a_contact_key_in_broken_json_is_masked() -> None:
    assert mask_value('{"email_or_phone": 67997890123, "order_id": 7') == (
        '{"email_or_phone": *********23, "order_id": 7'
    )
    assert mask_value('{"contact": 5, "x"') == '{"contact": ***, "x"'


# --- Codes and hashes are not phones ---------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "0f1e2d3c4b5a69788776",
        "e3b0c4429812345678",
        "toolu_01A2345678901bc",
        "call_12345678",
        "a716-446655440000",
        "x" * 40 + "67997890123",
    ],
)
def test_digits_glued_to_a_run_with_a_digit_or_a_very_long_run_are_a_code(text: str) -> None:
    assert mask_value(text) == text


@pytest.mark.parametrize(
    ("text", "masked"),
    [
        ("ab1234567890", "ab********90"),
        ("sess-ab12345678", "sess-ab******78"),
        ("550e8400-e29b-41d4-a716-ab1234567890", "550e8400-e29b-41d4-a716-ab********90"),
        ("sku YMH12345678", "sku YMH******78"),
        ("pedido-12345678", "pedido-******78"),
    ],
)
def test_codes_glued_only_to_letters_are_over_masked_in_free_text_by_design(
    text: str, masked: str
) -> None:
    """Accepted false positive: masking too much is safe, leaking a phone is not.

    Hashes and ids the code produces are protected by `TRUSTED_KEYS` instead.
    """
    assert mask_value(text) == masked


def _hex_digest(seed: str, length: int) -> str:
    """Deterministic pseudo-random hex, the shape of `static_prompt_hash`."""
    return hashlib.sha256(seed.encode()).hexdigest()[:length]


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("fone99789-0123", "fone*****-**23"),
        ("Fone:99789-0123", "Fone:*****-**23"),
        ("TEL67997890123", "TEL*********23"),
        ("CARLOS67997890123", "CARLOS*********23"),
        ("meuzap67997890123", "meuzap*********23"),
        ("v12345678", "v******78"),
        ("liga67997890123", "liga*********23"),
        ("Retorno:\\n67997890123", "Retorno:\\n*********23"),
        ("Retorno:\\f67997890123", "Retorno:\\f*********23"),
        ("n\\u00ba67997890123", "n\\u00ba*********23"),
        ("ligue 99789-0123-obrigado", "ligue *****-**23-obrigado"),
    ],
)
def test_phones_glued_to_words_labels_or_escapes_are_still_masked(raw: str, masked: str) -> None:
    assert mask_value(raw) == masked


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("0xx67 99789-0123", "*xx** *****-**23"),
        ("0XX67 99789-0123", "*XX** *****-**23"),
        ("0xx(67) 99789-0123", "*xx(**) *****-**23"),
        ("(0xx67) 99789-0123", "(*xx**) *****-**23"),
        ("0xx67997890123", "*xx*********23"),
        ("ddd67 99789-0123", "ddd** *****-**23"),
        ("DDD 67 99789-0123", "DDD ** *****-**23"),
    ],
)
def test_phones_with_a_0xx_or_ddd_prefix_are_masked(raw: str, masked: str) -> None:
    assert mask_value(raw) == masked
    assert mask_value(f"Fone {raw}.") == f"Fone {masked}."


def test_a_0xx_phone_inside_json_arguments_is_masked() -> None:
    masked = mask_value(json.dumps({"description": "Fone 0xx67 99789-0123"}))

    assert isinstance(masked, str)
    assert json.loads(masked) == {"description": "Fone *xx** *****-**23"}


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("Carlos,67997890123", "Carlos,*********23"),
        ("tel.67997890123", "tel.*********23"),
        ("fone-67997890123", "fone-*********23"),
        ("fone-(67) 99789-0123", "fone-(**) *****-**23"),
    ],
)
def test_a_dot_comma_or_dash_after_a_letter_does_not_shield_a_phone(raw: str, masked: str) -> None:
    assert mask_value(raw) == masked


def test_a_refused_code_match_does_not_hide_a_phone_right_after_it() -> None:
    assert mask_value("ref a1b2 x9 67997890123") == "ref a1b2 x9 *********23"
    assert mask_value("a1+5567997890123") == "a1+***********23"


@pytest.mark.parametrize(
    "text",
    [
        "1a12345678 " * 10_000,
        "a1" + "b12345678" * 11_000,
        ("x9" * 20 + "67997890123 ") * 2_000,
        "0xx" * 35_000,
        "9-" * 50_000,
        "a,1" * 35_000,
    ],
)
def test_many_refused_matches_stay_linear(text: str) -> None:
    started = time.perf_counter()
    mask_value(text)

    assert time.perf_counter() - started < 0.5


def test_trusted_code_generated_fields_are_never_masked() -> None:
    for seed in range(5_000):
        digest = _hex_digest(f"prompt-{seed}", 12)  # includes all-digit and ab1234... hashes
        data = {
            "model": "claude-sonnet-4-5-20250929",
            "prompt_hash": digest,
            "prompt_version": "67997890123",
            "tool_call_id": "toolu_67997890123",
            "latency_ms": 67997890123,
            "error_type": "TimeoutError",
        }
        assert mask_event_data("llm_call", data) == data


def test_untrusted_fields_with_trusted_names_inside_results_are_still_masked() -> None:
    data = {"name": "get_product", "result": {"model": "67997890123", "prompt_hash": "joao@x.com"}}

    assert mask_event_data("tool_call", data)["result"] == {
        "model": "*********23",
        "prompt_hash": "j***@x***.com",
    }


# --- Absurd nesting falls back to text --------------------------------------------------


def test_json_too_deep_to_parse_is_masked_as_text() -> None:
    deep = "[" * 100_000 + '"joao@gmail.com"' + "]" * 100_000

    masked = mask_value(deep)

    assert isinstance(masked, str)
    assert "joao@gmail.com" not in masked
    assert "j***@g***.com" in masked


def test_json_that_parses_but_is_too_deep_to_walk_is_masked_as_text() -> None:
    deep = '{"a": ' * 900 + '"joao@gmail.com"' + "}" * 900

    masked = mask_value(deep)

    assert isinstance(masked, str)
    assert "joao@gmail.com" not in masked


def test_a_python_structure_too_deep_to_walk_is_replaced_not_raised() -> None:
    deep: object = "joao@gmail.com"
    for _ in range(5_000):
        deep = [deep]

    masked = mask_event_data("tool_call", {"name": "t", "result": deep, "ok": True})

    assert masked == {"name": "t", "result": "[not logged: nested too deeply]", "ok": True}
