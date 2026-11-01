"""Masking of personal data before it reaches the audit log (ADR-0004).

Pure functions, applied to every value of every event before it is written.
Two complementary layers, both cheap and with no state:

- By content: e-mails and Brazilian phone numbers are found by regex inside any
  string (a tool result, a Customer message, JSON serialized in a string).
- By key: values under keys known to hold personal data are masked whatever they
  look like (`contact` may be "zap do joao"). Customer names are masked this way:
  `customer_first_name` (get_order result) always, and `name` only in the
  arguments of `register_complaint` (elsewhere `name` is a Product name).

Formats keep just enough for auditing:

- e-mail: first letter of the local part and of the first domain label, then the
  rest of the domain: `joao@gmail.com` -> `j***@g***.com`;
- phone: every digit becomes `*` except the last two, separators are kept:
  `+55 (67) 99789-0123` -> `+** (**) *****-**23`;
- value under a key that matches neither: `***`.

Known limitations (ticket 12 repeats them in the README):

- Names outside tool data are logged as typed. A name written in free text in a
  Customer message ("sou o Carlos") cannot be detected reliably. Lia's own answers
  (`final_response`) carry the first name of a verified Customer and, in a
  Reclamação, the name the Customer gave. Only tool data is masked by key.
- A name in a Reclamação `description` is free text too.
- Text that is not valid JSON is masked by regex only, so a name under a key is
  masked there just for the keys the regex finds (`"key": "value"` pairs).

The store's own public phone, (67) 3341-4444, is kept as is: it is not personal
data and masking it would only hide the fallback the Lia gives to Customers.
A string that is valid JSON (tool arguments, serialized results) is parsed, masked
as a structure (keys honoured, escapes like `\\n` and `\\u00e3` already decoded) and
serialized again; anything else is masked textually. E-mail matching is Unicode
(`joão@x.com`) and linear: the left boundary keeps the scan from restarting inside
long runs of word characters.

Phones. A phone is a whole run of 8 to 11 digits, optionally with +55, a DDD
(`67`, `(67)`, `067`, `0xx67`, `0xx(67)`) and separators (space, `.`, `-`, en/em
dash), with no letter or decimal fraction on the right. On the left it may not
touch a digit or `_`, nor a `.`, `,` or `-` that follows a digit (decimals like
`12345678.50`, dates, UUID groups, `claude-sonnet-4-5-20250929`); a `.`, `,` or `-`
after a letter does not shield it (`Carlos,6799...`, `tel.6799...`, `fone-6799...`).
The date in a Protocolo (`EMP-20260323-K7XMQ2`) is never a phone.

Letters glued on the left are judged by the run of ASCII letters/digits they belong
to (`_continues_a_code`), with one rule: the run is a code, and the digits are left
alone, when it contains a digit (`0f1e2d3c4b5a69788776`, `toolu_01A...`) or is 32+
characters long. Anything else is still a phone: `fone99789-0123`, `CARLOS6799...`,
`ddd67 99789-0123`. A JSON escape right before the digits (`\\n`, `\\t`, `\\u00ba`,
in JSON text that could not be parsed) never makes a code. A refused match does
not hide what follows: the search restarts one character after the refused start.

Masking too much is a safe failure; missing a phone is not. So in free text (the
Customer's message, the model's answer, tool arguments) a code glued only to
letters is masked: `ab1234567890`, the last UUID group of `...-a716-ab1234567890`,
`YMH12345678`, `pedido-12345678`, and any all-digit run of 8 to 14 digits. The
catalog and Order data have no such codes (checked over all 65 Products and 20
Orders), and fields the code itself produces (`TRUSTED_KEYS`: model, prompt
hash/version, durations, tokens...) are never masked, so a hash cannot be corrupted
whatever its digits. Only top-level event fields are trusted, never keys inside tool
results or arguments.

Known phone leaks (limitations): digits glued to a run that already has a digit
(`pedido7fone67997890123`, `a1b67997890123`) or to 32+ letters, and formats outside the pattern
(foreign numbers; `+55 67 9 9789 0123` masks only `9789 0123`; a phone split by words).

Personal data under a key is masked whatever its JSON type: a phone sent as a number
(`{"email_or_phone": 67997890123}`) becomes the string `"*********23"`, lists and
objects under the key are masked leaf by leaf, `null` and booleans are kept.

Absurdly nested data (deeper than the interpreter recursion limit) never drops an
event: JSON text is then masked as plain text, and a Python structure is replaced
by `DEEP_MARKER`.
"""

import json
import re
from collections.abc import Callable, Mapping
from functools import cache

MASKED = "***"
DEEP_MARKER = "[not logged: nested too deeply]"
STORE_PHONES = frozenset({"6733414444", "33414444"})

CONTACT_KEYS = frozenset({"email_or_phone", "contact", "email", "phone"})
NAME_KEYS = frozenset({"customer_first_name"})
# Keys that are a person's name only inside the arguments of these tools.
ARGUMENT_NAME_KEYS: Mapping[str, frozenset[str]] = {"register_complaint": frozenset({"name"})}
# Top-level event fields written by our own code (Assistant, LLM adapter), never by the
# Customer or a tool: logged as is. `name`/`tool_calls` are not here: the model picks them.
# `tool_call_id` is not emitted today; it is listed so adding it cannot corrupt it.
TRUSTED_KEYS = frozenset(
    {
        "model",
        "prompt_hash",
        "prompt_version",
        "tool_call_id",
        "round",
        "ok",
        "error_type",
        "latency_ms",
        "duration_ms",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cache_read_tokens",
        "cache_creation_tokens",
    }
)
_MAX_GLUED = 32  # an alphanumeric run this long is a code; also bounds the backward scan
_ESCAPE_BEFORE = re.compile(r"\\(?:u[0-9a-fA-F]{4}|[A-Za-z])\Z")

# The lookbehind stops the match from starting at every position of a long run of
# word characters (without it the scan is quadratic). `\\uXXXX` keeps escaped
# non-ASCII letters (JSON text that could not be parsed) inside the local part.
_EMAIL = re.compile(r"(?<![\w.+-])((?:[\w.+-]|\\u[0-9a-fA-F]{4})+)@([\w-]+)((?:\.[\w-]+)+)")
_PHONE = re.compile(
    # Left: not after a digit or `_`, nor after a `.`, `,` or `-` that follows a digit
    # (decimals, dates, UUID groups); not the date of a Protocolo (`EMP-20260323-...`).
    r"(?<![\d_])(?<!\d[.,-])(?<!EMP-)"
    r"(?:\+?55[ .-]?)?"
    # DDD: 67, (67), 067, (067), 0xx67, (0xx67), 0xx(67).
    r"(?:(?:0[xX]{2}[ .-]?)?(?:\((?:0[xX]{2}|0)?\d{2}\)|0?\d{2})[ .-]?)?"
    r"9?\d{4}(?:\s?[-\u2013\u2014]\s?|[ .])?\d{4}"
    # Right: no letter/digit glued on, no decimal fraction (BRKR1122334BR, 12345678.50).
    r"(?!\w|[.,]\d)",
    re.ASCII,
)


def mask_value(value: object, *, name_keys: frozenset[str] = frozenset()) -> object:
    """Mask a JSON-like value; `name_keys` are extra keys holding a person's name."""
    if isinstance(value, str):
        return _mask_text(value, name_keys)
    if isinstance(value, Mapping):
        return {str(key): _mask_entry(str(key), item, name_keys) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [mask_value(item, name_keys=name_keys) for item in value]
    if value is None or isinstance(value, bool | int | float):
        return value
    return _mask_text(str(value), name_keys)  # anything else is logged as text


def mask_event_data(event_type: str, data: Mapping[str, object]) -> dict[str, object]:
    """Mask the payload of an event; tool arguments get the tool's own name keys."""
    tool = data.get("name") if event_type == "tool_call" else None
    argument_keys = ARGUMENT_NAME_KEYS.get(tool, frozenset()) if isinstance(tool, str) else None
    masked: dict[str, object] = {}
    for key, value in data.items():
        if key in TRUSTED_KEYS:
            masked[key] = value
            continue
        name_keys = (argument_keys or frozenset()) if key == "arguments" else frozenset()
        try:
            masked[key] = mask_value(value, name_keys=name_keys)
        except RecursionError:
            masked[key] = DEEP_MARKER
    return masked


def _mask_entry(key: str, value: object, name_keys: frozenset[str]) -> object:
    if key in CONTACT_KEYS:
        return _mask_personal(value, _mask_contact)
    if key in NAME_KEYS or key in name_keys:
        return _mask_personal(value, _mask_name)
    return mask_value(value, name_keys=name_keys)


def _mask_personal(value: object, mask: Callable[[str], str]) -> object:
    """A value under a personal-data key: every leaf is masked, whatever its JSON type."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, Mapping):
        return {str(key): _mask_personal(item, mask) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_mask_personal(item, mask) for item in value]
    return mask(str(value))  # numbers (a phone sent as a JSON number) and anything else


def _mask_contact(value: str) -> str:
    masked = _mask_by_content(value)
    return masked if masked != value else MASKED


def _mask_name(value: str) -> str:
    return MASKED if value else value


def _mask_text(text: str, name_keys: frozenset[str]) -> str:
    parsed = _parse_json_container(text)
    if parsed is not None:
        # Valid JSON in a string (tool arguments, serialized results): mask the
        # structure, so keys are honoured and escapes (`\\n`, `\\u00e3`) are real characters.
        try:
            return json.dumps(mask_value(parsed, name_keys=name_keys), ensure_ascii=False)
        except RecursionError:
            pass  # parses, but too deep to walk: mask it as text below
    return _mask_by_content(_keyed_string(name_keys).sub(_mask_keyed_match, text))


def _parse_json_container(text: str) -> dict[str, object] | list[object] | None:
    stripped = text.lstrip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        parsed: object = json.loads(stripped)
    except (ValueError, RecursionError):  # not JSON, or nested past the recursion limit
        return None
    if isinstance(parsed, dict):
        return {str(key): value for key, value in parsed.items()}
    return parsed if isinstance(parsed, list) else None


def _mask_by_content(text: str) -> str:
    text = _EMAIL.sub(_mask_email, text)
    # Not `_PHONE.sub`: a match refused as a code must not swallow the text after its
    # start (`0xx67 99789-0123`), so the search restarts one character later. Each
    # refusal advances at least one character and costs a bounded amount of work.
    out: list[str] = []
    pos = 0
    while (match := _PHONE.search(text, pos)) is not None:
        if _continues_a_code(text, match.start()):
            out.append(text[pos : match.start() + 1])
            pos = match.start() + 1
            continue
        out.append(text[pos : match.start()])
        out.append(_mask_phone(match[0]))
        pos = match.end()
    out.append(text[pos:])
    return "".join(out)


@cache
def _keyed_string(name_keys: frozenset[str]) -> re.Pattern[str]:
    """`"key": "value"` or `"key": 123` for every key holding personal data (JSON as text)."""
    keys = "|".join(re.escape(key) for key in sorted(CONTACT_KEYS | NAME_KEYS | name_keys))
    return re.compile(
        rf'"(?P<key>{keys})"(?P<sep>\s*:\s*)'
        r'(?:"(?P<value>(?:[^"\\]|\\.)*)"|(?P<number>-?\d[\d.eE+-]*))'
    )


def _mask_keyed_match(match: re.Match[str]) -> str:
    key, value, number = match["key"], match["value"], match["number"]
    mask = _mask_contact if key in CONTACT_KEYS else _mask_name
    if number is not None:
        return f'"{key}"{match["sep"]}{mask(number)}'
    return f'"{key}"{match["sep"]}"{mask(value)}"'


def _mask_email(match: re.Match[str]) -> str:
    local, label, suffix = match.groups()
    return f"{local[0]}***@{label[0]}***{suffix}"


def _mask_phone(text: str) -> str:
    digits = re.sub(r"\D", "", text)
    if digits.removeprefix("55").removeprefix("0") in STORE_PHONES or digits in STORE_PHONES:
        return text
    seen = 0
    out: list[str] = []
    for char in reversed(text):
        if char.isdigit():
            seen += 1
            out.append(char if seen <= 2 else "*")
        else:
            out.append(char)
    return "".join(reversed(out))


def _continues_a_code(text: str, start: int) -> bool:
    """Whether the digits at `start` continue a code (hash, id), not a phone.

    One rule over the ASCII letters/digits glued right before `start`: a code when
    the run contains a digit or is `_MAX_GLUED`+ long. A JSON escape right before
    `start` (`\\n`, `\\u00ba`) is never a code. The backward scan stops after
    `_MAX_GLUED` characters, so the check is constant time per match.
    """
    begin = start
    while begin > 0 and start - begin < _MAX_GLUED:
        char = text[begin - 1]
        if not (char.isascii() and char.isalnum()):
            break
        begin -= 1
    glued = text[begin:start]
    if not glued or _ESCAPE_BEFORE.search(text, max(0, start - 6), start):
        return False
    return len(glued) >= _MAX_GLUED or any(char.isdigit() for char in glued)
