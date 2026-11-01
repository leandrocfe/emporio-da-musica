"""`get_order` tool: Order verification in code and the verified Order output.

The model's arguments go to `verify_order` unvalidated on purpose: an invalid
`order_id` ("7", -7, true) must be a counted failure with the same generic
result as a nonexistent Order (ADR-0003). Raising `ToolArgumentError` here
would give the model a different, `invalid_arguments` result. Only the
registry's generic checks (unknown or missing keys) answer with a tool error;
they never depend on the Order, so they reveal nothing about it.

Verified output carries the Customer's first name only, never the e-mail,
phone, full name or city. Money leaves as a decimal string in reais (ADR-0002);
dates as ISO 8601. The post-sale windows are computed with the store's
calendar day of `ctx.now` (ADR-0005).
"""

from collections.abc import Mapping
from datetime import date

from emporio.clock import STORE_TIMEZONE
from emporio.money import to_brl
from emporio.orders import (
    LOCKED,
    OrderRecord,
    OrderRepository,
    Refusal,
    Verified,
    verify_order,
)
from emporio.post_sale import PostSaleWindows, Window, post_sale_windows
from emporio.store_info import STORE_EMAIL, STORE_PHONE
from emporio.tools import ToolContext, ToolRegistry, ToolResult

HUMAN_HANDOFF_CONTACTS = f"telefone {STORE_PHONE} ou e-mail {STORE_EMAIL}"

# One result for every denied case, identical field by field: nothing in it
# depends on the Order, the contact or the reason.
DENIED_MESSAGE = (
    "Não foi possível verificar o Pedido com os dados informados. Peça ao Cliente para "
    "conferir o número do Pedido e o e-mail ou telefone do cadastro, sem dizer qual dado "
    "não confere nem se o Pedido existe."
)
LOCKED_MESSAGE = (
    "Limite de tentativas de verificação desta conversa atingido; nenhum Pedido pode ser "
    "consultado nela. Oriente o Cliente a falar com a equipe da loja (Atendimento humano) "
    f"pelo {HUMAN_HANDOFF_CONTACTS}."
)

GET_ORDER_DESCRIPTION = (
    "Consulta um Pedido com Verificação do pedido: exige o número do Pedido e o e-mail ou "
    "telefone do cadastro, ambos informados pelo Cliente nesta conversa. Verificado, "
    "retorna `verified: true`, `order` (primeiro nome do Cliente, status, data, Itens do "
    "pedido, `total` = Valor do pedido gravado, em reais como string decimal, forma de "
    "pagamento, rastreio, `estimated_delivery` = Entrega prevista e `notes` = observações "
    "ou motivo do cancelamento), `post_sale_windows` com `reference_date` e os prazos já "
    "calculados: `withdrawal` (arrependimento, 7 dias da Entrega prevista), "
    "`defect_exchange` (troca por defeito, 30 dias da data do Pedido) e `legal_warranty` "
    "(garantia legal, 90 dias da Entrega prevista), cada um com `until` (último dia "
    "dentro do prazo), `within` e `borderline`; os três vêm null se o Pedido não está "
    "`delivered` (sem prazo de pós-venda a informar); e `overdue` "
    "(Pedido enviado com Entrega prevista vencida). Não verificado: `verified: false` e "
    "`message`; com `locked: true` a conversa não pode mais consultar Pedidos."
)

GET_ORDER_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "order_id": {
            "type": "integer",
            "minimum": 1,
            "description": "Número do Pedido informado pelo Cliente (ex.: 7).",
        },
        "email_or_phone": {
            "type": "string",
            "description": (
                "E-mail ou telefone do cadastro, exatamente como o Cliente informou "
                '(ex.: "(67) 99999-0000").'
            ),
        },
    },
    "required": ["order_id", "email_or_phone"],
    "additionalProperties": False,
}


def register_order_tools(registry: ToolRegistry, orders: OrderRepository) -> None:
    def get_order(args: Mapping[str, object], ctx: ToolContext) -> ToolResult:
        outcome = verify_order(
            orders, ctx.session, args.get("order_id"), args.get("email_or_phone")
        )
        if isinstance(outcome, Refusal):
            return _refusal(outcome)
        today = ctx.now.astimezone(STORE_TIMEZONE).date()
        return _verified(outcome, today)

    registry.register("get_order", GET_ORDER_DESCRIPTION, GET_ORDER_SCHEMA, get_order)


def _refusal(refusal: Refusal) -> ToolResult:
    # A new dict every call: a caller mutating one result never changes the next.
    if refusal is LOCKED:
        return {"verified": False, "locked": True, "message": LOCKED_MESSAGE}
    return {"verified": False, "locked": False, "message": DENIED_MESSAGE}


def _verified(outcome: Verified, today: date) -> ToolResult:
    order = outcome.order
    found = post_sale_windows(order.status, order.order_date, order.estimated_delivery, today)
    return {
        "verified": True,
        "order": _order(order),
        "post_sale_windows": _windows(found, today),
        "overdue": found.overdue,
    }


def _order(order: OrderRecord) -> ToolResult:
    return {
        "id": order.id,
        "customer_first_name": _first_name(order.owner.name),
        "status": order.status,
        "order_date": order.order_date.isoformat(),
        "items": [
            {"product_id": item.product_id, "name": item.product_name, "quantity": item.quantity}
            for item in order.items
        ],
        "total": to_brl(order.total),
        "payment_method": order.payment_method,
        "tracking_code": order.tracking_code,
        "estimated_delivery": (
            order.estimated_delivery.isoformat() if order.estimated_delivery else None
        ),
        "notes": order.notes,
    }


def _windows(found: PostSaleWindows, today: date) -> ToolResult:
    return {
        "reference_date": today.isoformat(),
        "withdrawal": _window(found.withdrawal),
        "defect_exchange": _window(found.defect_exchange),
        "legal_warranty": _window(found.legal_warranty),
    }


def _window(window: Window | None) -> ToolResult | None:
    if window is None:
        return None
    return {
        "until": window.until.isoformat(),
        "within": window.within,
        "borderline": window.borderline,
    }


def _first_name(full_name: str) -> str:
    parts = full_name.split()
    return parts[0] if parts else ""
