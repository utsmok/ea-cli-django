"""
Tests for API views, focusing on bug fixes for file upload validation.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from apps.api.views import _validate_uploaded_file, trigger_ingest


class TestFileUploadValidation:
    """Test file upload validation for size and extension limits."""

    def test_validate_missing_file(self):
        """Test that missing file is properly rejected."""
        is_valid, error_msg = _validate_uploaded_file(None)
        assert not is_valid
        assert error_msg == "Missing 'file' upload"

    def test_validate_file_size_exceeds_limit(self):
        """Test that files exceeding 100MB limit are rejected."""
        # Create a file that's larger than 100MB
        large_content = b"x" * (101 * 1024 * 1024)  # 101MB
        uploaded = SimpleUploadedFile("large.xlsx", large_content)

        is_valid, error_msg = _validate_uploaded_file(uploaded)
        assert not is_valid
        assert "100MB limit" in error_msg

    def test_validate_file_size_within_limit(self):
        """Test that files within 100MB limit are accepted."""
        # Create a small file
        content = b"test content"
        uploaded = SimpleUploadedFile("small.xlsx", content)

        is_valid, error_msg = _validate_uploaded_file(uploaded)
        assert is_valid
        assert error_msg is None

    def test_validate_allowed_extensions(self):
        """Test that only allowed file extensions are accepted."""
        allowed_extensions = [".xlsx", ".xls", ".csv"]

        for ext in allowed_extensions:
            content = b"test content"
            uploaded = SimpleUploadedFile(f"test{ext}", content)
            is_valid, _error_msg = _validate_uploaded_file(uploaded)
            assert is_valid, f"Extension {ext} should be allowed"

    def test_validate_disallowed_extensions(self):
        """Test that disallowed file extensions are rejected."""
        disallowed_extensions = [".pdf", ".txt", ".exe", ".zip", ".doc"]

        for ext in disallowed_extensions:
            content = b"test content"
            uploaded = SimpleUploadedFile(f"test{ext}", content)
            is_valid, error_msg = _validate_uploaded_file(uploaded)
            assert not is_valid, f"Extension {ext} should be rejected"
            assert "Invalid file type" in error_msg

    def test_validate_extension_case_insensitive(self):
        """Test that extension validation is case-insensitive."""
        content = b"test content"
        uploaded = SimpleUploadedFile("TEST.XLSX", content)

        is_valid, error_msg = _validate_uploaded_file(uploaded)
        assert is_valid
        assert error_msg is None

    def test_validate_no_extension(self):
        """Test that files without extension are rejected."""
        content = b"test content"
        uploaded = SimpleUploadedFile("noextension", content)

        is_valid, error_msg = _validate_uploaded_file(uploaded)
        assert not is_valid
        assert "Invalid file type" in error_msg


class TestTriggerIngestView:
    """Test trigger_ingest view with file validation."""

    pytestmark = pytest.mark.django_db

    def test_trigger_ingest_rejects_missing_file(self):
        """Test that trigger_ingest returns 400 for missing file."""
        factory = RequestFactory()
        request = factory.post("/api/ingest/", {})

        response = trigger_ingest(request)
        assert response.status_code == 400

    def test_trigger_ingest_rejects_invalid_extension(self):
        """Test that trigger_ingest rejects invalid file types."""
        factory = RequestFactory()
        content = b"test content"
        uploaded = SimpleUploadedFile("test.pdf", content)

        request = factory.post("/api/ingest/", {"file": uploaded})

        response = trigger_ingest(request)
        assert response.status_code == 400
        assert b"Invalid file type" in response.content

    def test_trigger_ingest_rejects_oversized_file(self):
        """Test that trigger_ingest rejects files exceeding size limit."""
        factory = RequestFactory()
        # Create file slightly larger than 100MB
        large_content = b"x" * (101 * 1024 * 1024)
        uploaded = SimpleUploadedFile("large.xlsx", large_content)

        request = factory.post("/api/ingest/", {"file": uploaded})

        response = trigger_ingest(request)
        assert response.status_code == 400
        assert b"100MB limit" in response.content
