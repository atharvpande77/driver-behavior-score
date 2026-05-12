from enum import StrEnum
from dataclasses import dataclass


class AuthType(StrEnum):
    DASHBOARD = "dashboard"
    API_KEY = "api_key"


@dataclass(frozen=True)
class AuthTokens:
    email: str
    name: str
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int