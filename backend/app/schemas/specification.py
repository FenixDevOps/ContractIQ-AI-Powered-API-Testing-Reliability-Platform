from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SpecificationOut(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: str | None
    openapi_version: str
    api_version: str
    original_filename: str
    file_format: str
    version_number: int
    content_hash: str
    imported_at: datetime
    endpoint_count: int = 0
    validation_status: str = "valid"
