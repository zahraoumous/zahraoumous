from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Credentials(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def valid_password(cls, value: str) -> str:
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ValueError("Password must contain valid Unicode characters") from None
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Enter a valid email address")
        if (
            len(value.split("@")) != 2
            or not all(value.split("@"))
            or any(c.isspace() for c in value)
        ):
            raise ValueError("Enter a valid email address")
        if "." not in value.split("@")[1]:
            raise ValueError("Enter a valid email address")
        return value


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def meaningful_name(cls, value: str) -> str:
        if not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Name cannot be blank")
        return value.strip()


class Identity(BaseModel):
    id: UUID
    email: str
    display_name: str | None


class WorkspaceCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def meaningful_name(cls, value: str) -> str:
        if not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Name cannot be blank")
        return value.strip()


class Workspace(BaseModel):
    id: UUID
    name: str
    role: str


class ImportFile(BaseModel):
    id: UUID
    path: str
    filename: str
    status: str
    progress: int
    job_id: UUID
    dataset_id: UUID
    dataset_version_id: UUID
    error_code: str | None
    error_message: str | None


class ImportBatch(BaseModel):
    id: UUID
    name: str
    status: str
    total_files: int
    created_at: datetime
    files: list[ImportFile]


class DatasetSummary(BaseModel):
    id: UUID
    name: str
    status: str
    version_id: UUID
    row_count: int | None
    column_count: int | None
    created_at: datetime
    source_path: str


class DatasetColumn(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    type: str
    null_count: int


class QualityFinding(BaseModel):
    rule_code: str
    severity: str
    column_name: str | None
    affected_rows: int
    details: dict[str, Any]


class DatasetDetail(DatasetSummary):
    columns: list[DatasetColumn]
    preview: list[dict[str, Any]]
    quality: list[QualityFinding]
    sha256: str
    profile: dict[str, Any]
