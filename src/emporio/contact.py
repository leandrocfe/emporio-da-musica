"""Contact normalization for the Order verification (`order verification`, ADR-0003).

A contact containing `@` is an e-mail (lowercase, no whitespace). Anything else
is a phone: non-digits removed, a leading `55` removed when 13 digits remain,
then one leading `0` removed. Only two lengths are accepted: 11 digits (DDD +
number), compared with the whole stored phone, and 9 digits (number without
DDD), compared with the last 9 digits of the stored phone. Every other length
(landlines, typos, foreign numbers) is unusable and normalizes to `None`,
which the verification treats as a failure.

The stored phone goes through the same normalization, so a stored value in any
accepted format compares the same way.
"""

import re
from dataclasses import dataclass

_NON_DIGIT = re.compile(r"\D")
_COUNTRY_CODE = "55"
FULL_PHONE_DIGITS = 11  # DDD + number
LOCAL_PHONE_DIGITS = 9  # number without DDD


@dataclass(frozen=True, slots=True)
class Email:
    value: str


@dataclass(frozen=True, slots=True)
class Phone:
    digits: str  # FULL_PHONE_DIGITS or LOCAL_PHONE_DIGITS long


Contact = Email | Phone


def normalize_contact(raw: str) -> Contact | None:
    """The contact the Customer typed, normalized; `None` when it is unusable."""
    if "@" in raw:
        email = normalize_email(raw)
        # An address needs something on both sides of the `@`.
        local, _, domain = email.partition("@")
        return Email(email) if local and domain else None
    digits = normalize_phone(raw)
    return Phone(digits) if digits is not None else None


def normalize_email(raw: str) -> str:
    return "".join(raw.split()).lower()


def normalize_phone(raw: str) -> str | None:
    """Digits of an accepted phone (11 or 9 long), or `None`."""
    digits = _NON_DIGIT.sub("", raw)
    if len(digits) == 13 and digits.startswith(_COUNTRY_CODE):
        digits = digits[len(_COUNTRY_CODE) :]
    if digits.startswith("0"):
        digits = digits[1:]
    if len(digits) in (FULL_PHONE_DIGITS, LOCAL_PHONE_DIGITS):
        return digits
    return None


def contact_matches(contact: Contact, *, email: str, phone: str) -> bool:
    """Whether `contact` is the stored e-mail or phone of the Customer."""
    if isinstance(contact, Email):
        stored_email = normalize_email(email)
        return bool(stored_email) and contact.value == stored_email
    stored = normalize_phone(phone)
    if stored is None:
        return False
    if len(contact.digits) == FULL_PHONE_DIGITS:
        return contact.digits == stored
    return stored[-LOCAL_PHONE_DIGITS:] == contact.digits
