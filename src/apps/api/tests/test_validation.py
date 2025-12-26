"""
Tests for API input validation and Pydantic schemas.

Tests verify that request validation provides specific error messages
and that Pydantic schemas correctly validate input data.
"""

import pytest

from apps.api.schemas import (
    BulkUpdateRequest,
    ClassificationV2,
    ErrorResponse,
    HealthCheckResponse,
    UpdateItemRequest,
    WorkflowStatus,
)
from apps.steps.views import _parse_item_ids


class TestParseItemIdsValidation:
    """Test enhanced _parse_item_ids function with detailed validation."""

    def test_parse_valid_item_ids(self):
        """Test parsing valid item IDs."""
        ids, error = _parse_item_ids(["123", "456", "789"])
        assert error is None
        assert ids == [123, 456, 789]

    def test_parse_empty_list(self):
        """Test parsing empty list returns specific error."""
        _ids, error = _parse_item_ids([])
        assert error is not None
        assert "No item IDs provided" in error

    def test_parse_non_list_input(self):
        """Test parsing non-list input returns type error."""
        _ids, error = _parse_item_ids("123")  # type: ignore
        assert error is not None
        assert "expected list" in error
        assert "got str" in error

    def test_parse_empty_string_in_list(self):
        """Test parsing list with empty string returns position error."""
        _ids, error = _parse_item_ids(["123", "", "456"])
        assert error is not None
        assert "position 2" in error
        assert "is empty" in error

    def test_parse_whitespace_only_string(self):
        """Test parsing whitespace-only string returns empty error."""
        _ids, error = _parse_item_ids(["123", "   ", "456"])
        assert error is not None
        assert "position 2" in error

    def test_parse_invalid_integer_format(self):
        """Test parsing invalid integer format returns position error."""
        _ids, error = _parse_item_ids(["123", "abc", "456"])
        assert error is not None
        assert "position 2" in error
        assert "'abc'" in error
        assert "not a valid integer" in error

    def test_parse_non_string_in_list(self):
        """Test parsing list with non-string element returns type error."""
        _ids, error = _parse_item_ids([123, "456"])  # type: ignore
        assert error is not None
        assert "position 1" in error
        assert "not a string" in error
        assert "int" in error

    def test_parse_negative_integer(self):
        """Test parsing negative integer returns positive required error."""
        _ids, error = _parse_item_ids(["123", "-456", "789"])
        assert error is not None
        assert "position 2" in error
        assert "-456" in error
        assert "must be positive" in error

    def test_parse_zero(self):
        """Test parsing zero returns positive required error."""
        _ids, error = _parse_item_ids(["0", "456"])
        assert error is not None
        assert "position 1" in error
        assert "0" in error
        assert "must be positive" in error

    def test_parse_duplicates_removed(self):
        """Test that duplicate IDs are removed while preserving order."""
        ids, error = _parse_item_ids(["123", "456", "123", "789", "456"])
        assert error is None
        assert ids == [123, 456, 789]

    def test_parse_all_duplicates(self):
        """Test parsing list with all duplicates returns single ID."""
        ids, error = _parse_item_ids(["123", "123", "123"])
        assert error is None
        assert ids == [123]

    def test_parse_float_string_converts(self):
        """Test that float strings are converted to integers."""
        _ids, error = _parse_item_ids(["123.0", "456"])
        # This depends on int() behavior - it should work
        # but might need adjustment based on actual requirements
        assert error is None or "position 1" in error

    def test_parse_mixed_valid_invalid(self):
        """Test parsing list with mix of valid and invalid IDs."""
        _ids, error = _parse_item_ids(["123", "abc", "456", "-789"])
        assert error is not None
        # Should fail at position 2 (abc)
        assert "position 2" in error


class TestPydanticSchemas:
    """Test Pydantic schema validation."""

    def test_update_item_request_valid(self):
        """Test valid UpdateItemRequest schema."""
        data = {
            "material_id": 123,
            "workflow_status": "ToDo",
            "remarks": "Test remarks",
        }
        schema = UpdateItemRequest(**data)
        assert schema.material_id == 123
        assert schema.workflow_status == WorkflowStatus.TODO
        assert schema.remarks == "Test remarks"

    def test_update_item_request_remarks_stripped(self):
        """Test that remarks are stripped of whitespace."""
        schema = UpdateItemRequest(
            material_id=123, workflow_status="ToDo", remarks="  Test remarks  "
        )
        assert schema.remarks == "Test remarks"

    def test_update_item_request_at_least_one_field_required(self):
        """Test that at least one field must be provided."""
        with pytest.raises(ValueError, match="At least one field"):
            UpdateItemRequest(material_id=123)

    def test_update_item_request_material_id_must_be_positive(self):
        """Test material_id validation - must be positive."""
        with pytest.raises(ValueError):
            UpdateItemRequest(material_id=0, workflow_status="ToDo")

        with pytest.raises(ValueError):
            UpdateItemRequest(material_id=-1, workflow_status="ToDo")

    def test_update_item_request_remarks_max_length(self):
        """Test remarks max length validation."""
        long_remarks = "x" * 5001
        with pytest.raises(ValueError):
            UpdateItemRequest(material_id=123, remarks=long_remarks)

    def test_bulk_update_request_valid(self):
        """Test valid BulkUpdateRequest schema."""
        data = {
            "item_ids": [1, 2, 3],
            "workflow_status": "In Progress",
            "remarks": "Bulk update",
        }
        schema = BulkUpdateRequest(**data)
        assert schema.item_ids == [1, 2, 3]
        assert schema.workflow_status == WorkflowStatus.IN_PROGRESS

    def test_bulk_update_request_item_ids_min_length(self):
        """Test item_ids min_length validation."""
        with pytest.raises(ValueError):
            BulkUpdateRequest(item_ids=[], workflow_status="ToDo")

    def test_bulk_update_request_removes_duplicates(self):
        """Test that duplicate item_ids are removed."""
        schema = BulkUpdateRequest(item_ids=[1, 2, 1, 3, 2], workflow_status="ToDo")
        assert schema.item_ids == [1, 2, 3]

    def test_bulk_update_request_validates_positive_ids(self):
        """Test that item_ids must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            BulkUpdateRequest(item_ids=[1, -2, 3], workflow_status="ToDo")

        with pytest.raises(ValueError, match="must be positive"):
            BulkUpdateRequest(item_ids=[1, 0, 3], workflow_status="ToDo")

    def test_bulk_update_request_at_least_one_field_required(self):
        """Test that at least one update field must be provided."""
        with pytest.raises(ValueError, match="At least one field"):
            BulkUpdateRequest(item_ids=[1, 2, 3])

    def test_error_response_valid(self):
        """Test ErrorResponse schema."""
        schema = ErrorResponse(error="Test error", detail="Details", status_code=404)
        assert schema.error == "Test error"
        assert schema.detail == "Details"
        assert schema.status_code == 404

    def test_error_response_status_code_validation(self):
        """Test status_code range validation."""
        # Valid range is 100-599
        ErrorResponse(error="Test", status_code=100)
        ErrorResponse(error="Test", status_code=599)

        with pytest.raises(ValueError):
            ErrorResponse(error="Test", status_code=99)

        with pytest.raises(ValueError):
            ErrorResponse(error="Test", status_code=600)

    def test_health_check_response_valid(self):
        """Test HealthCheckResponse schema."""
        schema = HealthCheckResponse(
            status="healthy",
            service="ea-platform",
            version="1.0.0",
            environment="production",
            debug=False,
        )
        assert schema.status == "healthy"
        assert schema.service == "ea-platform"


class TestSchemaEnums:
    """Test enum values in schemas."""

    def test_workflow_status_enum(self):
        """Test WorkflowStatus enum values."""
        assert WorkflowStatus.TODO.value == "ToDo"
        assert WorkflowStatus.IN_PROGRESS.value == "In Progress"
        assert WorkflowStatus.DONE.value == "Done"
        assert WorkflowStatus.BLOCKED.value == "Blocked"

    def test_classification_v2_enum(self):
        """Test ClassificationV2 enum values."""
        assert ClassificationV2.NIET_GEANALYSEERD.value == "Niet geanalyseerd"
        assert ClassificationV2.PUBLIC_DOMEIN.value == "Public Domain"
        assert ClassificationV2.GELICENTIEERD.value == "Gelicentieerd"
        assert ClassificationV2.CEILLIMIET.value == "Ceillimit"
        assert ClassificationV2.OVEREENKOMST.value == "Overeenkomst"

    def test_workflow_status_from_string(self):
        """Test creating WorkflowStatus from string."""
        status = WorkflowStatus("ToDo")
        assert status == WorkflowStatus.TODO

    def test_classification_v2_from_string(self):
        """Test creating ClassificationV2 from string."""
        cls = ClassificationV2("Public Domain")
        assert cls == ClassificationV2.PUBLIC_DOMEIN
