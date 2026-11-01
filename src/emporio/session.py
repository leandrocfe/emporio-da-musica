"""Session (`session`): one Customer conversation in one browser tab."""

from dataclasses import dataclass, field

from emporio.llm import Message


@dataclass
class Session:
    """Conversation state owned by the UI and handed to the Assistant.

    `history` holds only user/assistant/tool messages (the system prompt is
    rebuilt on every model call). Per-session state of later tickets (e.g. the
    failed Order verification counter, ticket 06) is added here as new fields.
    """

    id: str
    history: list[Message] = field(default_factory=list)
