"""Web entrypoint: the sample storefront page at `/` with the Lia chat mounted at `/lia`.

Run with `uvicorn emporio.web:app`. The chat (`emporio.chat`) is a Chainlit app mounted
on the same FastAPI instance, so the page can embed it in an iframe on the same origin.
"""

from pathlib import Path

from chainlit.utils import mount_chainlit
from fastapi import FastAPI
from fastapi.responses import FileResponse

_PACKAGE_DIR = Path(__file__).resolve().parent
_INDEX_HTML = _PACKAGE_DIR / "static" / "index.html"
_CHAT_SCRIPT = _PACKAGE_DIR / "chat.py"

app = FastAPI(title="Empório da Música")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_INDEX_HTML, media_type="text/html")


# Mounted after the `/` route so the storefront page is not shadowed by Chainlit.
mount_chainlit(app=app, target=str(_CHAT_SCRIPT), path="/lia")
