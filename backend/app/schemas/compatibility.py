from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ComparisonCreate(BaseModel):
    old_specification_id: UUID
    new_specification_id: UUID

    @model_validator(mode="after")
    def specifications_must_differ(self):
        if self.old_specification_id == self.new_specification_id:
            raise ValueError("Choose two different specifications.")
        return self


class ComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    old_specification_id: UUID
    new_specification_id: UUID
    compatibility_score: int = Field(ge=0, le=100)
    overall_status: str
    total_changes: int
    breaking_changes: int
    non_breaking_changes: int
    potentially_breaking_changes: int
    informational_changes: int
    comparison_metadata: dict
    created_at: datetime


class ComparisonChangesPage(BaseModel):
    items: list[dict]
    page: int
    page_size: int
    total: int
