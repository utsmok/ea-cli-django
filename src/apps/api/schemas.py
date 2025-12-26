"""
Pydantic schemas for API request/response validation.

Uses Django Shinobi (django-ninja) for type-safe API validation
and automatic OpenAPI documentation generation.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class ClassificationV2(str, Enum):
    """V2 classification options for copyright items."""

    NIET_GEANALYSEERD = "Niet geanalyseerd"
    PUBLIC_DOMEIN = "Public Domain"
    GELICENTIEERD = "Gelicentieerd"
    CEILLIMIET = "Ceillimit"
    OVEREENKOMST = "Overeenkomst"


class WorkflowStatus(str, Enum):
    """Workflow status options for copyright items."""

    TODO = "ToDo"
    IN_PROGRESS = "In Progress"
    DONE = "Done"
    BLOCKED = "Blocked"


# Request Schemas
class UpdateItemRequest(BaseModel):
    """Request schema for updating a single copyright item."""

    material_id: int = Field(..., gt=0, description="Material ID (must be positive)")
    workflow_status: WorkflowStatus | None = Field(
        None, description="New workflow status"
    )
    v2_manual_classification: ClassificationV2 | None = Field(
        None, description="V2 classification"
    )
    remarks: str | None = Field(None, max_length=5000, description="Optional remarks")

    @field_validator("remarks")
    @classmethod
    def clean_remarks(cls, v: str | None) -> str | None:
        """Strip whitespace from remarks."""
        return v.strip() if v else None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UpdateItemRequest":
        """Ensure at least one field is being updated."""
        if not any(
            [
                self.workflow_status is not None,
                self.v2_manual_classification is not None,
                self.remarks is not None,
            ]
        ):
            raise ValueError("At least one field must be provided for update")
        return self


class BulkUpdateRequest(BaseModel):
    """Request schema for bulk updating copyright items."""

    item_ids: list[int] = Field(..., min_length=1, description="List of material IDs")
    workflow_status: WorkflowStatus | None = None
    v2_manual_classification: ClassificationV2 | None = None
    remarks: str | None = Field(None, max_length=5000)

    @field_validator("item_ids")
    @classmethod
    def validate_item_ids(cls, v: list[int]) -> list[int]:
        """Validate all item IDs are positive and remove duplicates."""
        if not v:
            raise ValueError("item_ids cannot be empty")

        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for item_id in v:
            if item_id <= 0:
                raise ValueError(f"Invalid item_id: {item_id} (must be positive)")
            if item_id not in seen:
                seen.add(item_id)
                unique_ids.append(item_id)

        return unique_ids

    @field_validator("remarks")
    @classmethod
    def clean_remarks(cls, v: str | None) -> str | None:
        """Strip whitespace from remarks."""
        return v.strip() if v else None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "BulkUpdateRequest":
        """Ensure at least one field is being updated."""
        if not any(
            [
                self.workflow_status is not None,
                self.v2_manual_classification is not None,
                self.remarks is not None,
            ]
        ):
            raise ValueError("At least one field must be provided for update")
        return self


# Response Schemas
class ItemResponse(BaseModel):
    """Response schema for a single copyright item."""

    material_id: int
    filename: str | None
    title: str | None
    workflow_status: WorkflowStatus
    v2_manual_classification: ClassificationV2 | None
    faculty: str | None
    file_exists: bool | None

    model_config = {"from_attributes": True}


class BulkUpdateResponse(BaseModel):
    """Response schema for bulk update operations."""

    success: bool
    updated_count: int
    errors: list[str] = Field(default_factory=list)
    message: str


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str
    detail: str | None = None
    status_code: int = Field(..., ge=100, le=599)


class HealthCheckResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: str
    service: str
    version: str
    environment: str
    debug: bool


class ReadinessCheckResponse(BaseModel):
    """Response schema for readiness check endpoint."""

    status: str
    checks: dict[str, str]
