"""Seam — contact normalization and matching for the Order verification (ADR-0003)."""

import pytest

from emporio.contact import Email, Phone, contact_matches, normalize_contact

# Customer 14 (owner of Order 7) as stored by the seed.
STORED_EMAIL = "leticia.rocha@jmail.com"
STORED_PHONE = "67997890123"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+55 (67) 99789-0123", Phone("67997890123")),
        ("5567997890123", Phone("67997890123")),
        ("67997890123", Phone("67997890123")),
        ("(067) 99789-0123", Phone("67997890123")),
        ("99789-0123", Phone("997890123")),
        ("997890123", Phone("997890123")),
        (" Leticia.Rocha @JMail.com ", Email("leticia.rocha@jmail.com")),
    ],
)
def test_contact_is_normalized_per_adr_0003(raw: str, expected: Email | Phone) -> None:
    assert normalize_contact(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "abc",
        "9789-0123",  # 8 digits
        "6799789012",  # 10 digits
        "556799789012",  # 12 digits
        "55679978901234",  # 14 digits
        "4467997890123",  # 13 digits without the country code 55
        "@",
    ],
)
def test_unusable_contact_normalizes_to_none(raw: str) -> None:
    assert normalize_contact(raw) is None


@pytest.mark.parametrize(
    "raw", ["leticia.rocha@jmail.com", "+55 (67) 99789-0123", "67997890123", "997890123"]
)
def test_owner_contact_matches(raw: str) -> None:
    contact = normalize_contact(raw)

    assert contact is not None
    assert contact_matches(contact, email=STORED_EMAIL, phone=STORED_PHONE)


@pytest.mark.parametrize(
    "raw",
    [
        "leticia.rocha@jmail.com.br",
        "rocha@jmail.com",
        "67997890124",
        "11997890123",  # same number, other DDD
        "997890124",
        "897890123",
    ],
)
def test_other_contact_does_not_match(raw: str) -> None:
    contact = normalize_contact(raw)

    assert contact is not None
    assert not contact_matches(contact, email=STORED_EMAIL, phone=STORED_PHONE)


def test_stored_phone_is_normalized_the_same_way() -> None:
    contact = normalize_contact("67997890123")

    assert contact is not None
    assert contact_matches(contact, email=STORED_EMAIL, phone="+55 (67) 99789-0123")


def test_stored_phone_that_does_not_normalize_never_matches() -> None:
    contact = normalize_contact("997890123")

    assert contact is not None
    assert not contact_matches(contact, email=STORED_EMAIL, phone="0123")
