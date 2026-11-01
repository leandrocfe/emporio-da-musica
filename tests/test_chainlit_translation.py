import json
import tomllib
from pathlib import Path

import chainlit

from emporio.store_info import STORE_PHONE

CHAINLIT_DIR = Path(__file__).resolve().parent.parent / ".chainlit"

WATERMARK = (
    "A Lia pode cometer erros. Verifique sempre as informações e, em caso de "
    "dúvidas, entre em contato pelo telefone/WhatsApp (67) 3341-4444."
)


def test_pt_br_watermark_has_store_phone() -> None:
    data = json.loads((CHAINLIT_DIR / "translations" / "pt-BR.json").read_text("utf-8"))
    assert data["chat"]["watermark"] == WATERMARK
    assert STORE_PHONE in data["chat"]["watermark"]


def test_config_uses_pt_br() -> None:
    config = tomllib.loads((CHAINLIT_DIR / "config.toml").read_text("utf-8"))
    assert config["UI"]["language"] == "pt-BR"


def _flatten(node: object, prefix: str = "") -> set[str]:
    if isinstance(node, dict):
        keys: set[str] = set()
        for key, value in node.items():
            keys |= _flatten(value, f"{prefix}.{key}" if prefix else key)
        return keys
    return {prefix}


def test_pt_br_keys_match_chainlit_en_us() -> None:
    reference = Path(chainlit.__file__).parent / "translations" / "en-US.json"
    ours = json.loads((CHAINLIT_DIR / "translations" / "pt-BR.json").read_text("utf-8"))
    theirs = json.loads(reference.read_text("utf-8"))
    assert _flatten(ours) == _flatten(theirs)
