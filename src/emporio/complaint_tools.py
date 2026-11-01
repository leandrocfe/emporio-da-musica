"""`register_complaint` tool: validation and output of the Reclamação registration.

The only tool that writes. `order_id` is a free reference (ADR-0003): it is
stored as given (text), never looked up, and nothing about an Order is
returned. The output is just the Protocolo and the response deadline as text.
"""

from collections.abc import Mapping

from emporio.complaints import ComplaintService, collapse_whitespace
from emporio.tools import ToolArgumentError, ToolContext, ToolRegistry, ToolResult

RESPONSE_DEADLINE = "até 24 horas úteis"
MAX_NAME_LENGTH = 120
MAX_CONTACT_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 2000
MAX_ORDER_REFERENCE_LENGTH = 40

REGISTER_COMPLAINT_DESCRIPTION = (
    "Registra uma Reclamação do Cliente e devolve o Protocolo e o prazo de retorno. Use só "
    "depois de ter coletado, nesta conversa, o nome, o contato (e-mail ou telefone) e a "
    "descrição do problema; `order_id` é opcional e é só uma referência anotada, não é "
    "verificada. Retorna `protocol` e `response_deadline` (texto). Repetir a mesma descrição "
    "na mesma conversa devolve o mesmo Protocolo."
)

REGISTER_COMPLAINT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Nome do Cliente."},
        "contact": {"type": "string", "description": "E-mail ou telefone para retorno."},
        "description": {"type": "string", "description": "Descrição do problema."},
        "order_id": {
            "type": ["string", "integer"],
            "description": "Número do Pedido, se o Cliente informou (opcional).",
        },
    },
    "required": ["name", "contact", "description"],
    "additionalProperties": False,
}


def register_complaint_tools(registry: ToolRegistry, complaints: ComplaintService) -> None:
    def register_complaint(args: Mapping[str, object], ctx: ToolContext) -> ToolResult:
        protocol = complaints.register(
            session_id=ctx.session.id,
            name=_text(args, "name", MAX_NAME_LENGTH),
            contact=_text(args, "contact", MAX_CONTACT_LENGTH),
            description=_text(args, "description", MAX_DESCRIPTION_LENGTH),
            order_id=_order_reference(args.get("order_id")),
            now=ctx.now,
        )
        return {"protocol": protocol, "response_deadline": RESPONSE_DEADLINE}

    registry.register(
        "register_complaint",
        REGISTER_COMPLAINT_DESCRIPTION,
        REGISTER_COMPLAINT_SCHEMA,
        register_complaint,
    )


def _text(args: Mapping[str, object], key: str, max_length: int) -> str:
    value = args.get(key)
    if not isinstance(value, str):
        raise ToolArgumentError(f"`{key}` deve ser um texto.")
    text = collapse_whitespace(value)
    if not text:
        raise ToolArgumentError(f"`{key}` não pode ser vazio.")
    if len(text) > max_length:
        raise ToolArgumentError(f"`{key}` deve ter no máximo {max_length} caracteres.")
    return text


def _order_reference(value: object) -> str | None:
    if value is None:
        return None
    # bool is a subclass of int in Python: `true` is not a reference.
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ToolArgumentError("`order_id` deve ser o número do Pedido (texto ou inteiro).")
    reference = collapse_whitespace(str(value))
    if len(reference) > MAX_ORDER_REFERENCE_LENGTH:
        raise ToolArgumentError(
            f"`order_id` deve ter no máximo {MAX_ORDER_REFERENCE_LENGTH} caracteres."
        )
    return reference or None
