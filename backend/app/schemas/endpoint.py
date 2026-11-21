from uuid import UUID
from pydantic import BaseModel


class EndpointOut(BaseModel):
    id: UUID
    specification_id: UUID
    path: str
    method: str
    operation_id: str | None
    summary: str | None
    description: str | None
    tags: list
    parameters: list
    request_body: dict | None
    responses: dict
    deprecated: bool
    security: list
