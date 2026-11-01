"""Session (`session`): one Customer conversation in one browser tab."""

import threading
from dataclasses import dataclass, field

from emporio.llm import Message


@dataclass
class Session:
    """Conversation state owned by the UI and handed to the Assistant.

    `history` holds only user/assistant/tool messages (the system prompt is
    rebuilt on every model call). `failed_verifications` counts failed Order
    verifications of this Session; it only grows (ADR-0003) and reaches the
    tools through `ToolContext.session`, never through model arguments.

    `verification_lock` makes "check the lock, verify, count the failure" atomic:
    the UI runs each reply in a worker thread, so two messages of the same tab
    may verify at once. It is not state: left out of `repr` and equality, and a
    copy (or unpickled Session) gets a fresh lock of its own.
    """

    id: str
    history: list[Message] = field(default_factory=list)
    failed_verifications: int = 0
    verification_lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False, compare=False
    )

    def __getstate__(self) -> dict[str, object]:
        state = dict(self.__dict__)
        del state["verification_lock"]  # locks cannot be copied or pickled
        return state

    def __setstate__(self, state: dict[str, object]) -> None:
        self.__dict__.update(state)
        self.verification_lock = threading.Lock()
