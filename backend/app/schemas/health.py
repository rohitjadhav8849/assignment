from typing import Literal

from pydantic import BaseModel


class RootResponse(BaseModel):
    name: str
    status: Literal["ok"]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class DependencyStatus(BaseModel):
    status: Literal["available", "unavailable"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, DependencyStatus]
