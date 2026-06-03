from __future__ import annotations

import secrets


def make_token() -> str:
    return secrets.token_urlsafe(32)
