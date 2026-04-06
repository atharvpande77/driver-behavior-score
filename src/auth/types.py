from dataclasses import dataclass


@dataclass(frozen=True)
class AuthTokens:
    email: str
    name: str
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int
