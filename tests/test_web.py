from fastapi.testclient import TestClient

from emporio.web import app

client = TestClient(app)


def test_index_embeds_lia_iframe() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<iframe id="lia-frame" src="/lia"' in response.text


def test_index_has_no_mock_chat_or_out_of_scope_content() -> None:
    html = client.get("/").text

    for forbidden in (
        "Acessórios",
        "Áudio",
        "pode cometer erros",
        "lia-form",
        "lia-input",
        "function reply",
        "Entrar",
        "Favoritos",
    ):
        assert forbidden not in html
    assert 'role="search"' not in html
