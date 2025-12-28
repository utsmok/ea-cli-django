"""
Visual regression tests.

These tests take screenshots of key UI states to establish a visual baseline.
Screenshots can be manually reviewed or used with automated diffing tools.

Screenshots are saved to: test_screenshots/
"""

import pytest
from playwright.sync_api import Page

pytestmark = pytest.mark.playwright


class TestDashboardScreenshots:
    """Take screenshots of dashboard states."""

    def test_dashboard_default_view(self, authenticated_page: Page, base_url: str, screenshot_dir, sample_data):
        """Screenshot: Default dashboard view with sample data."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "dashboard_default_view.png"), full_page=True)

    def test_dashboard_with_filters(self, authenticated_page: Page, base_url: str, screenshot_dir, sample_data):
        """Screenshot: Dashboard with filters applied."""
        authenticated_page.goto(f"{base_url}/dashboard/?status=ToDo&faculty=EEMCS")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "dashboard_filtered_view.png"), full_page=True)

    def test_dashboard_detail_panel(self, authenticated_page: Page, base_url: str, screenshot_dir, sample_data):
        """Screenshot: Dashboard with detail panel open."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Click first row to open detail panel
        first_row = authenticated_page.locator("table tbody tr").first
        if first_row.is_visible():
            first_row.click()
            authenticated_page.wait_for_timeout(500)

        authenticated_page.screenshot(path=str(screenshot_dir / "dashboard_detail_panel.png"), full_page=True)


class TestStepsScreenshots:
    """Take screenshots of steps UI."""

    def test_steps_index_page(self, authenticated_page: Page, base_url: str, screenshot_dir):
        """Screenshot: Steps index page showing all 7 steps."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "steps_index.png"), full_page=True)

    def test_step_1_qlik_ingestion(self, authenticated_page: Page, base_url: str, screenshot_dir):
        """Screenshot: Step 1 Qlik ingestion page."""
        authenticated_page.goto(f"{base_url}/steps/ingest-qlik/")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "step_1_qlik_ingestion.png"), full_page=True)

    def test_step_3_osiris_enrichment(self, authenticated_page: Page, base_url: str, screenshot_dir):
        """Screenshot: Step 3 Osiris enrichment page."""
        authenticated_page.goto(f"{base_url}/steps/enrich-osiris/")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "step_3_osiris_enrichment.png"), full_page=True)

    def test_step_7_export_faculty(self, authenticated_page: Page, base_url: str, screenshot_dir):
        """Screenshot: Step 7 export faculty page."""
        authenticated_page.goto(f"{base_url}/steps/export-faculty/")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "step_7_export_faculty.png"), full_page=True)


class TestModalScreenshots:
    """Take screenshots of modal dialogs."""

    def test_upload_modal(self, authenticated_page: Page, base_url: str, screenshot_dir):
        """Screenshot: Upload modal dialog."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Open upload modal
        upload_button = authenticated_page.locator("button:has-text('Upload Excel')").first
        upload_button.click()

        # Wait for modal animation
        authenticated_page.wait_for_selector(".modal", state="visible")
        authenticated_page.wait_for_timeout(300)

        authenticated_page.screenshot(path=str(screenshot_dir / "modal_upload.png"))

    def test_login_page(self, page: Page, base_url: str, screenshot_dir):
        """Screenshot: Login page."""
        page.goto(f"{base_url}/accounts/login/")
        page.wait_for_load_state("networkidle")

        page.screenshot(path=str(screenshot_dir / "page_login.png"), full_page=True)


class TestResponsiveDesign:
    """Test responsive design at different viewports."""

    def test_dashboard_mobile_viewport(self, authenticated_page: Page, base_url: str, screenshot_dir, sample_data):
        """Screenshot: Dashboard at mobile viewport (375x667)."""
        authenticated_page.set_viewport_size({"width": 375, "height": 667})
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "dashboard_mobile_375x667.png"), full_page=True)

    def test_dashboard_tablet_viewport(self, authenticated_page: Page, base_url: str, screenshot_dir, sample_data):
        """Screenshot: Dashboard at tablet viewport (768x1024)."""
        authenticated_page.set_viewport_size({"width": 768, "height": 1024})
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "dashboard_tablet_768x1024.png"), full_page=True)

    def test_steps_mobile_viewport(self, authenticated_page: Page, base_url: str, screenshot_dir):
        """Screenshot: Steps index at mobile viewport."""
        authenticated_page.set_viewport_size({"width": 375, "height": 667})
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "steps_mobile_375x667.png"), full_page=True)


class TestTableLayout:
    """Test table layout and rendering."""

    def test_table_layout_desktop(self, authenticated_page: Page, base_url: str, screenshot_dir, sample_data):
        """Screenshot: Table layout at desktop viewport."""
        authenticated_page.set_viewport_size({"width": 1920, "height": 1080})
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "table_desktop_1920x1080.png"), full_page=True)

    def test_table_with_pagination(self, authenticated_page: Page, base_url: str, screenshot_dir, sample_data):
        """Screenshot: Table with pagination visible."""
        authenticated_page.goto(f"{base_url}/dashboard/?per_page=5")
        authenticated_page.wait_for_load_state("networkidle")

        authenticated_page.screenshot(path=str(screenshot_dir / "table_paginated.png"), full_page=True)


class TestColorSchemes:
    """Test that UI elements have proper colors and contrast."""

    def test_workflow_tab_colors(self, authenticated_page: Page, base_url: str, screenshot_dir):
        """Screenshot: Workflow tabs with active states."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Crop to just the tabs area
        tabs = authenticated_page.locator(".tabs").first
        tabs.screenshot(path=str(screenshot_dir / "ui_workflow_tabs.png"))

    def test_step_card_colors(self, authenticated_page: Page, base_url: str, screenshot_dir):
        """Screenshot: Step cards with different badge colors."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Crop to just the first few cards
        first_card = authenticated_page.locator(".card").first
        first_card.screenshot(path=str(screenshot_dir / "ui_step_card.png"))
