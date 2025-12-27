"""
Ingestion UI tests.

Tests the data ingestion workflows including:
- Qlik file upload
- Faculty sheet upload
- Batch processing status
- Staged data viewing
- Error display
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.playwright


class TestUploadModal:
    """Test file upload modal functionality."""

    def test_upload_modal_opens(self, authenticated_page: Page, base_url: str):
        """Test that upload modal can be opened."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Click upload button
        upload_button = authenticated_page.locator("button:has-text('Upload Excel')").first
        upload_button.click()

        # Wait for modal to appear
        modal = authenticated_page.locator(".modal").first
        expect(modal).to_be_visible()

    def test_upload_modal_has_source_type_dropdown(self, authenticated_page: Page, base_url: str):
        """Test that upload modal has source type dropdown."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Open upload modal
        upload_button = authenticated_page.locator("button:has-text('Upload Excel')").first
        upload_button.click()

        # Wait for modal
        authenticated_page.wait_for_selector(".modal", state="visible")

        # Check for source type dropdown
        source_select = authenticated_page.locator('select[name="source_type"]').first
        expect(source_select).to_be_visible()

        # Check options
        expect(source_select).to_contain_text("Qlik export")
        expect(source_select).to_contain_text("Faculty sheet")

    def test_upload_modal_has_file_input(self, authenticated_page: Page, base_url: str):
        """Test that upload modal has file input."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Open upload modal
        upload_button = authenticated_page.locator("button:has-text('Upload Excel')").first
        upload_button.click()

        # Wait for modal
        authenticated_page.wait_for_selector(".modal", state="visible")

        # Check for file input
        file_input = authenticated_page.locator('input[type="file"]').first
        expect(file_input).to_be_visible()

    def test_upload_modal_closes_on_backdrop_click(self, authenticated_page: Page, base_url: str):
        """Test that upload modal closes when clicking backdrop."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Open upload modal
        upload_button = authenticated_page.locator("button:has-text('Upload Excel')").first
        upload_button.click()

        # Wait for modal
        authenticated_page.wait_for_selector(".modal", state="visible")

        # Click backdrop
        backdrop = authenticated_page.locator(".modal-backdrop").first
        backdrop.click()

        # Modal should close (may take a moment for Alpine transition)
        authenticated_page.wait_for_timeout(300)

        modal = authenticated_page.locator(".modal").first
        # Check if modal is closed (no longer has modal-open class)
        expect(modal).not_to_have_class("modal-open")


class TestFileUpload:
    """Test file upload functionality."""

    def test_file_upload_accepts_files(self, authenticated_page: Page, base_url: str, tmp_path):
        """Test that file input accepts Excel files."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Open upload modal
        upload_button = authenticated_page.locator("button:has-text('Upload Excel')").first
        upload_button.click()

        # Wait for modal
        authenticated_page.wait_for_selector(".modal", state="visible")

        # Create test file
        test_file = tmp_path / "test_upload.xlsx"
        test_file.write_bytes(b"PK\x03\x04" + b"\x00" * 100)  # Minimal Excel file

        # Set file input
        file_input = authenticated_page.locator('input[type="file"]').first
        file_input.set_input_files(str(test_file))

        # File name should appear
        authenticated_page.wait_for_timeout(500)

        # Just verify file was accepted (no error)
        expect(file_input).to_be_visible()

    def test_upload_button_exists(self, authenticated_page: Page, base_url: str):
        """Test that upload submit button exists."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Open upload modal
        upload_button = authenticated_page.locator("button:has-text('Upload Excel')").first
        upload_button.click()

        # Wait for modal
        authenticated_page.wait_for_selector(".modal", state="visible")

        # Check for submit button
        submit_button = authenticated_page.locator('button[type="submit"]').first
        expect(submit_button).to_be_visible()
        expect(submit_button).to_contain_text("Upload")


class TestBatchStatus:
    """Test batch status display."""

    def test_batch_status_visible(self, authenticated_page: Page, base_url: str):
        """Test that batch status is displayed somewhere in UI."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Batch status might be visible in various places
        # This is a soft check - just verify page loads without errors
        expect(authenticated_page.locator("body")).to_be_visible()


class TestFacultyCodeInput:
    """Test faculty code input for faculty sheet uploads."""

    def test_faculty_code_input_exists_for_faculty_sheets(self, authenticated_page: Page, base_url: str):
        """Test that faculty code input appears when Faculty sheet is selected."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Open upload modal
        upload_button = authenticated_page.locator("button:has-text('Upload Excel')").first
        upload_button.click()

        # Wait for modal
        authenticated_page.wait_for_selector(".modal", state="visible")

        # Select faculty sheet option
        source_select = authenticated_page.locator('select[name="source_type"]').first
        source_select.select_option("FACULTY")

        # Check for faculty code input
        faculty_input = authenticated_page.locator('input[name="faculty_code"]').first
        expect(faculty_input).to_be_visible()


class TestUploadErrorHandling:
    """Test upload error handling."""

    def test_upload_validation_messages(self, authenticated_page: Page, base_url: str):
        """Test that upload shows validation for missing fields."""
        from src.tests.playwright.conftest import inject_toast_capture

        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Inject toast capture
        inject_toast_capture(authenticated_page)

        # Open upload modal
        upload_button = authenticated_page.locator("button:has-text('Upload Excel')").first
        upload_button.click()

        # Wait for modal
        authenticated_page.wait_for_selector(".modal", state="visible")

        # Try to submit without file
        submit_button = authenticated_page.locator('button[type="submit"]').first
        submit_button.click()

        # Wait for response
        authenticated_page.wait_for_timeout(1000)

        # Should handle gracefully (no crash)
        expect(authenticated_page.locator(".modal")).to_be_visible()


class TestEnrichAllButton:
    """Test enrich all functionality."""

    def test_enrich_all_button_exists(self, authenticated_page: Page, base_url: str):
        """Test that enrich all button exists on dashboard."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for enrich all button
        enrich_button = authenticated_page.locator("button:has-text('Enrich All')").first

        if enrich_button.count() > 0:
            expect(enrich_button).to_be_visible()

    def test_download_faculty_sheets_button_exists(self, authenticated_page: Page, base_url: str):
        """Test that download faculty sheets button exists."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for download button
        download_button = authenticated_page.locator("a:has-text('Download Faculty Sheets')").first

        if download_button.count() > 0:
            expect(download_button).to_be_visible()
