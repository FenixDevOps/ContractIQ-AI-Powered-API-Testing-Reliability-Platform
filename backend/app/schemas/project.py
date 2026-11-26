from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Project name cannot be blank.")
        return normalized


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Project name cannot be blank.")
        return normalized


class ProjectInviteCreate(BaseModel):
    email: EmailStr
    role: Literal["ADMIN", "MEMBER", "VIEWER"] = "MEMBER"


class ProjectInviteAccept(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class ProjectRoleUpdate(BaseModel):
    role: Literal["ADMIN", "MEMBER", "VIEWER"]


class ProjectMemberOut(BaseModel):
    user_id: UUID
    full_name: str
    email: EmailStr
    role: str
    joined_at: datetime


class ProjectInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: str
    expires_at: datetime
    created_at: datetime


class ProjectActivityOut(BaseModel):
    id: UUID
    actor_name: str | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict
    created_at: datetime


class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    is_archived: bool = False
    owner_id: UUID | None = None
    current_user_role: str = "MEMBER"
    specification_count: int = 0
    latest_version: int | None = None
    endpoint_count: int = 0
