from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from uuid import UUID


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    name: str
    active: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    email: str
    name: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_in: int
    refresh_expires_in: int


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class RenameAPIKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None


class CreateAPIKeyResponse(APIKeyResponse):
    raw_key: str
    warning: str = "Store this key securely. It will not be shown again."
