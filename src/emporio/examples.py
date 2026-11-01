"""Example-conversation generator (ticket 11): `python -m emporio.examples`.

Runs the five scripted conversations (`SCRIPTS`) against the configured model
(`LLM_MODEL`) with a pinned reference date (`EXAMPLES_NOW`) and temperature 0,
then writes one Markdown file per conversation under `docs/conversas/`, with the
Customer/Lia turns and the matching excerpt of the audit log.

Each conversation gets a fresh `Session` and a fresh database seeded from the CSVs
(so the Complaint protocol of one run never depends on earlier runs). Events go
through the production `JsonlEventSink` into a temporary file and are read back,
so what is published is exactly what the audit log would hold: masked by
`emporio.masking`, tool results clipped the same way. The transcript is taken from
those masked events too. Limitation (same as the audit log, see `emporio.masking`):
only e-mails and phone numbers are masked in free text; a name typed by the Customer
or Lia's use of a verified Customer's first name are published as they are.

The files are only written after every conversation succeeded: a provider failure
(the Assistant turns it into a friendly fallback) aborts the run instead of
publishing a conversation that does not show the real behavior.
"""

import json
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from emporio.app import build_assistant
from emporio.assistant import EMPTY_ANSWER_FALLBACK, ROUND_LIMIT_FALLBACK
from emporio.audit_log import JsonlEventSink
from emporio.clock import parse_agent_now
from emporio.db import PROJECT_ROOT, data_dir_from_env
from emporio.llm import LLMClient
from emporio.seed import seed
from emporio.session import Session

EXAMPLES_NOW_ISO = "2026-03-23T10:00:00-04:00"
EXAMPLES_NOW = parse_agent_now(EXAMPLES_NOW_ISO)
TEMPERATURE = 0.0
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs" / "conversas"
_LOGGED_IN_EXCERPT = frozenset({"tool_call", "error"})


@dataclass(frozen=True, slots=True)
class ConversationScript:
    """A scripted conversation (roteiro): the Customer's messages, in order."""

    slug: str
    title: str
    summary: str
    turns: tuple[str, ...]


SCRIPTS: tuple[ConversationScript, ...] = (
    ConversationScript(
        slug="01-violoes-ate-mil-reais",
        title="Violões até R$ 1000: busca, PIX e produto esgotado",
        summary=(
            "O Cliente procura violões até R$ 1000, pergunta o valor no PIX de um dos "
            "resultados e depois pergunta por um modelo que não apareceu na lista "
            "(Giannini GF-3D), que está esgotado."
        ),
        turns=(
            "Oi! Estou procurando um violão de até R$ 1000. O que vocês têm?",
            "Gostei do Giannini GF-1R. Quanto fica pagando no PIX?",
            "Vi também o Giannini GF-3D Dreadnought Sunburst. Esse tem pra pronta entrega?",
        ),
    ),
    ConversationScript(
        slug="02-takamine-gd20-promocao-expirada",
        title="Takamine GD20 e uma Promoção expirada",
        summary=(
            "O Cliente lembra de uma promoção do Takamine GD20 que já terminou; a Lia "
            "deve oferecer apenas o Preço de tabela (ou o PIX), nunca a promoção expirada."
        ),
        turns=(
            "Boa tarde! Vi há um tempo uma promoção do violão Takamine GD20. "
            "Ainda está com desconto?",
            "Entendi. E em quantas vezes dá pra parcelar no cartão?",
        ),
    ),
    ConversationScript(
        slug="03-devolucao-pedido-7",
        title="Devolução do Pedido 7 com Verificação do pedido",
        summary=(
            "A Cliente quer devolver o Pedido 7. A Lia só revela dados do Pedido depois da "
            "Verificação do pedido (número do Pedido + e-mail do cadastro) e calcula os "
            "prazos de pós-venda: arrependimento vencido e garantia legal vigente."
        ),
        turns=(
            "Olá, comprei um ukulele aí na loja e quero devolver. É o Pedido 7.",
            "O e-mail do cadastro é leticia.rocha@jmail.com",
            "Ainda dá pra devolver por arrependimento? E se o ukulele tiver algum defeito, "
            "tenho garantia?",
        ),
    ),
    ConversationScript(
        slug="04-acessorios-e-fora-de-escopo",
        title="Acessórios e uma pergunta fora de escopo",
        summary=(
            "O Cliente pergunta por Acessórios (que a loja não vende) e depois faz uma "
            "pergunta Fora de escopo; a Lia recusa com gentileza e redireciona."
        ),
        turns=(
            "Oi, vocês vendem cordas de violão e cabo P10?",
            "Tá bom. Aproveitando, você sabe me dizer quem ganhou o jogo do Brasil ontem?",
        ),
    ),
    ConversationScript(
        slug="05-reclamacao-com-protocolo",
        title="Reclamação registrada com Protocolo",
        summary=(
            "A Cliente relata uma insatisfação; a Lia acolhe, coleta nome, contato e "
            "descrição, registra a Reclamação e informa o Protocolo e o prazo de retorno."
        ),
        turns=(
            "Estou muito chateado. Meu pedido atrasou e ninguém me deu retorno, "
            "quero fazer uma reclamação.",
            "Meu nome é Ana Carolina Ferreira, o e-mail é anacarol.ferreira@coldmail.com "
            "e o pedido é o 8. "
            "Ele deveria ter chegado e até agora nada, e ninguém atende o telefone.",
        ),
    ),
)


class ExampleGenerationError(RuntimeError):
    """A conversation hit a provider/runtime error; nothing should be published."""


def generate_conversation(
    script: ConversationScript,
    llm: LLMClient,
    data_dir: Path,
    now: datetime,
    work_dir: Path | None = None,
) -> str:
    """Run one script with a fresh Session and return its Markdown document."""
    if work_dir is None:
        with tempfile.TemporaryDirectory() as tmp:
            return generate_conversation(script, llm, data_dir, now, Path(tmp))
    db_path = work_dir / f"{script.slug}.db"
    log_path = work_dir / f"{script.slug}.audit.jsonl"
    log_path.unlink(missing_ok=True)
    seed(db_path, data_dir)
    assistant = build_assistant(
        llm, db_path, events=JsonlEventSink(log_path, clock=lambda: now), clock=lambda: now
    )
    session = Session(id=f"exemplo-{script.slug}")
    for message in script.turns:
        assistant.reply(session, message)
    events = [json.loads(line) for line in log_path.read_text("utf-8").splitlines()]
    if any(event["type"] == "error" for event in events):
        raise ExampleGenerationError(
            f"A conversa {script.slug!r} registrou erro no log (falha do modelo?); "
            "nada foi gravado. Confira LLM_MODEL e a chave do provedor."
        )
    if any(
        event["type"] == "final_response"
        and event.get("content") in (ROUND_LIMIT_FALLBACK, EMPTY_ANSWER_FALLBACK)
        for event in events
    ):
        raise ExampleGenerationError(
            f"A conversa {script.slug!r} terminou em resposta de contingência (limite de "
            "consultas ou resposta vazia); nada foi gravado."
        )
    return _render(script, events, now)


def generate_all(
    llm: LLMClient,
    output_dir: Path,
    data_dir: Path,
    now: datetime,
    scripts: Sequence[ConversationScript] = SCRIPTS,
) -> list[Path]:
    """Generate every conversation, then write them (and an index) to `output_dir`."""
    with tempfile.TemporaryDirectory() as tmp:
        documents = [
            (script, generate_conversation(script, llm, data_dir, now, Path(tmp)))
            for script in scripts
        ]
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for script, document in documents:
        path = output_dir / f"{script.slug}.md"
        path.write_text(document, encoding="utf-8")
        written.append(path)
    (output_dir / "README.md").write_text(_render_index(scripts, now), encoding="utf-8")
    return written


def _render(script: ConversationScript, events: list[dict[str, object]], now: datetime) -> str:
    model = next(
        (e.get("model") for e in events if e["type"] == "llm_call" and e.get("model")), None
    )
    lines = [
        f"# {script.title}",
        "",
        script.summary,
        "",
        f"- Data de referência: `{now.isoformat()}`",
        f"- Modelo: `{model or 'não informado'}`",
        f"- Temperatura: {TEMPERATURE:g}",
        "",
        "## Conversa",
        "",
    ]
    turns: list[list[dict[str, object]]] = []
    for event in events:
        if event["type"] == "customer_message":
            turns.append([])
        if turns:
            turns[-1].append(event)
    for turn in turns:
        for event in turn:
            if event["type"] == "customer_message":
                lines += [f"**Cliente:** {event['content']}", ""]
            elif event["type"] == "final_response":
                lines += [f"**Lia:** {event['content']}", ""]
    lines += [
        "## Log de auditoria",
        "",
        "Trecho do log de auditoria desta conversa (eventos `tool_call` e `error`), com "
        "e-mails e telefones mascarados pelo mesmo mascaramento do log em produção "
        "(nomes escritos em texto livre não são mascarados).",
        "",
    ]
    for number, turn in enumerate(turns, start=1):
        excerpt = [event for event in turn if event["type"] in _LOGGED_IN_EXCERPT]
        lines += [f"### Turno {number}", ""]
        if not excerpt:
            lines += ["_Nenhuma ferramenta foi chamada neste turno._", ""]
            continue
        for event in excerpt:
            lines += ["```json", json.dumps(event, ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines).rstrip() + "\n"


def _render_index(scripts: Sequence[ConversationScript], now: datetime) -> str:
    lines = [
        "# Conversas de exemplo",
        "",
        "Conversas da Lia geradas contra o modelo real, com Data de referência fixa "
        f"(`{now.isoformat()}`) e temperatura {TEMPERATURE:g}, cada uma com o trecho "
        "mascarado do log de auditoria. Para regenerar: "
        "`uv run --env-file .env python -m emporio.examples`.",
        "",
    ]
    lines += [f"{n}. [{s.title}]({s.slug}.md)" for n, s in enumerate(scripts, start=1)]
    return "\n".join(lines) + "\n"


def main() -> None:
    # Imported here: litellm is slow to import and only a real run needs it.
    from emporio.litellm_client import LiteLLMClient

    llm = LiteLLMClient.from_env(temperature=TEMPERATURE)
    written = generate_all(llm, DEFAULT_OUTPUT_DIR, data_dir_from_env(), EXAMPLES_NOW)
    for path in written:
        print(f"escrito: {path}")


if __name__ == "__main__":
    main()
