from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator
from datetime import datetime
from uuid import UUID


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        # Require at least one letter and at least one digit or special character
        has_letter = any(c.isalpha() for c in v)
        has_digit_or_special = any(not c.isalpha() for c in v)
        if not (has_letter and has_digit_or_special):
            raise ValueError("Password must contain at least one letter and one digit or special character.")
        return v


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    name: str = Field(max_length=128)
    active: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class UserMetadata(BaseModel):
    email: str
    name: str


class LoginResponse(BaseModel):
    user: UserMetadata
    access_expires_in: int


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
    expires_at: datetime | None = None


class CreateAPIKeyResponse(APIKeyResponse):
    raw_key: str
    warning: str = "Store this key securely. It will not be shown again."
