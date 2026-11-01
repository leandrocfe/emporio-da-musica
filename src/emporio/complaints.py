"""Reclamações (`complaints`): durable records with a readable Protocolo.

The only write path of the Assistant. Contract of `register`:

- Protocolo: `EMP-YYYYMMDD-XXXXXX`. The date is the store's calendar day of
  creation; the six characters are random (`secrets`) from an alphabet without
  look-alikes (no 0/O, 1/I/L, U/V). Random, not sequential, so a Protocolo
  reveals no volume and cannot be enumerated. Uniqueness is enforced by the
  database (`UNIQUE(protocol)`); a collision draws a new suffix.
- Idempotency: the same Sessão and the same description (compared after
  collapsing whitespace) is the same Reclamação and returns the same Protocolo.
  A repeat may correct name, contact and order_id of that row (upsert).
- Race safety: the Protocolo check and the upsert run in one `BEGIN IMMEDIATE`
  transaction (ADR-0002), so concurrent calls of one Sessão end with a single row.
- `order_id` is a free reference (ADR-0003): stored as text, never looked up.
"""

import secrets
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from emporio.clock import STORE_TIMEZONE
from emporio.db import connect, transaction

PROTOCOL_ALPHABET = "23456789ABCDEFGHJKMNPQRSTWXYZ"
PROTOCOL_SUFFIX_LENGTH = 6
MAX_PROTOCOL_ATTEMPTS = 20


@dataclass(frozen=True, slots=True)
class Complaint:
    protocol: str
    session_id: str
    name: str
    contact: str
    description: str
    order_id: str | None
    created_at: str  # ISO 8601 with offset


def random_suffix() -> str:
    return "".join(secrets.choice(PROTOCOL_ALPHABET) for _ in range(PROTOCOL_SUFFIX_LENGTH))


def collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


class ComplaintService:
    def __init__(self, db_path: Path, suffix: Callable[[], str] = random_suffix) -> None:
        self._db_path = db_path
        self._suffix = suffix

    def register(
        self,
        *,
        session_id: str,
        name: str,
        contact: str,
        description: str,
        order_id: str | None,
        now: datetime,
    ) -> str:
        """Save the Reclamação and return its Protocolo (the existing one if repeated).

        Arguments must already be validated and normalized (`collapse_whitespace`).
        """
        created_at = now.isoformat(timespec="seconds")
        day = f"{now.astimezone(STORE_TIMEZONE):%Y%m%d}"
        with connect(self._db_path) as conn, transaction(conn):
            for _ in range(MAX_PROTOCOL_ATTEMPTS):
                protocol = f"EMP-{day}-{self._suffix()}"
                if self._protocol_taken(conn, protocol):
                    continue  # never let a Protocolo collision touch another Reclamação
                # The conflict target is only (session, description): a repeat updates
                # name, contact and order_id of that row and keeps its Protocolo and
                # created_at. An omitted order_id does not erase the previous one.
                row = conn.execute(
                    "INSERT INTO complaints (protocol, session_id, name, contact, description,"
                    " order_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT (session_id, description) DO UPDATE SET"
                    " name = excluded.name, contact = excluded.contact,"
                    " order_id = COALESCE(excluded.order_id, complaints.order_id)"
                    " RETURNING protocol",
                    (protocol, session_id, name, contact, description, order_id, created_at),
                ).fetchone()
                return str(row["protocol"])
        raise RuntimeError("could not generate a unique Protocolo")

    def find_by_protocol(self, protocol: str) -> Complaint | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT protocol, session_id, name, contact, description, order_id, created_at"
                " FROM complaints WHERE protocol = ?",
                (protocol,),
            ).fetchone()
        return None if row is None else Complaint(**dict(row))

    @staticmethod
    def _protocol_taken(conn: sqlite3.Connection, protocol: str) -> bool:
        row = conn.execute("SELECT 1 FROM complaints WHERE protocol = ?", (protocol,)).fetchone()
        return row is not None
