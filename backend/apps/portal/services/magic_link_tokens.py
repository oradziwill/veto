"""Opaque one-time tokens for portal magic-link login (SHA-256 digest stored)."""

from __future__ import annotations

import hashlib
import secrets


def generate_magic_link_plaintext() -> str:
    return secrets.token_urlsafe(48)


def digest_magic_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
