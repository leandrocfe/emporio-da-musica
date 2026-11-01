"""`ToolRegistry` port: the Store tools the model may call (ADR-0001).

Each tool is registered with a name, a description, the JSON Schema of its
arguments and a handler `(args, ctx)`. New tools are registered; the
Assistant loop never changes.

The registry checks what is generic to every tool (arguments are a JSON
object, no unknown keys, required keys present); each handler validates the
types of its own arguments and raises `ToolArgumentError` with a message the
model can act on. Either way the model receives a structured error, never an
exception.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from emporio.events import EventSink
from emporio.session import Session

ToolResult = dict[str, object]  # JSON-serializable


@dataclass(frozen=True, slots=True)
class ToolContext:
    """What a handler gets besides the model's arguments.

    The Session always comes from here, never from the model (ADR-0001).
    """

    session: Session
    now: datetime  # Reference date (`now`)
    events: EventSink


ToolHandler = Callable[[Mapping[str, object], ToolContext], ToolResult]


class ToolArgumentError(ValueError):
    """Raised by a handler when the model sent arguments it cannot use."""


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, object]  # JSON Schema of the arguments object
    handler: ToolHandler


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    result: ToolResult
    ok: bool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, object],
        handler: ToolHandler,
    ) -> None:
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = Tool(name, description, parameters, handler)

    def definitions(self) -> list[dict[str, object]]:
        """Tool definitions in the OpenAI `tools` format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, raw_arguments: str, ctx: ToolContext) -> ToolOutcome:
        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(sorted(self._tools)) or "nenhuma"
            return _error(
                "unknown_tool", f"Ferramenta '{name}' não existe. Disponíveis: {available}."
            )
        try:
            args = _parse_arguments(raw_arguments, tool.parameters)
            return ToolOutcome(result=tool.handler(args, ctx), ok=True)
        except ToolArgumentError as exc:
            return _error("invalid_arguments", str(exc))


def _parse_arguments(raw: str, schema: Mapping[str, object]) -> dict[str, object]:
    try:
        parsed: object = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise ToolArgumentError(f"Argumentos não são JSON válido: {exc.msg}.") from exc
    if not isinstance(parsed, dict):
        raise ToolArgumentError("Argumentos devem ser um objeto JSON.")
    args: dict[str, object] = {str(key): value for key, value in parsed.items()}

    properties = schema.get("properties")
    known = set(properties) if isinstance(properties, dict) else set()
    unknown = sorted(set(args) - known)
    if unknown:
        raise ToolArgumentError(f"Argumentos desconhecidos: {', '.join(unknown)}.")
    required = schema.get("required")
    missing = [key for key in required if key not in args] if isinstance(required, list) else []
    if missing:
        raise ToolArgumentError(f"Argumentos obrigatórios ausentes: {', '.join(missing)}.")
    return args


def _error(code: str, message: str) -> ToolOutcome:
    return ToolOutcome(result={"error": {"code": code, "message": message}}, ok=False)
