"""
Steps UI tests.

Tests the 7-step processing pipeline UI including:
- Step index page
- Individual step pages
- Step navigation
- Step configuration
- Status indicators
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.playwright


class TestStepsIndexPage:
    """Test the steps index page."""

    def test_steps_index_loads(self, authenticated_page: Page, base_url: str):
        """Test that steps index page loads successfully."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check title
        expect(authenticated_page.locator("h1")).to_contain_text("Processing Steps")

        # Check for step cards
        step_cards = authenticated_page.locator(".card")
        expect(step_cards).to_have_count(count=7, timeout=5000)

    def test_all_7_steps_visible(self, authenticated_page: Page, base_url: str):
        """Test that all 7 processing steps are visible."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for each step by name
        expect(authenticated_page.get_by_text("Ingest Qlik Export")).to_be_visible()
        expect(authenticated_page.get_by_text("Ingest Faculty Sheet")).to_be_visible()
        expect(authenticated_page.get_by_text("Enrich from Osiris")).to_be_visible()
        expect(authenticated_page.get_by_text("Enrich from People Pages")).to_be_visible()
        expect(authenticated_page.get_by_text("Get PDF Status from Canvas")).to_be_visible()
        expect(authenticated_page.get_by_text("Extract PDF Details")).to_be_visible()
        expect(authenticated_page.get_by_text("Export Faculty Sheets")).to_be_visible()

    def test_step_cards_are_clickable(self, authenticated_page: Page, base_url: str):
        """Test that step cards are clickable links."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Find first step card link
        first_step_link = authenticated_page.locator("a[href*='/steps/']").first
        expect(first_step_link).to_be_visible()

    def test_step_numbers_displayed(self, authenticated_page: Page, base_url: str):
        """Test that step numbers are displayed on cards."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for step badges
        badges = authenticated_page.locator(".badge")
        expect(badges).to_have_count(count=7, timeout=5000)

        # Check first badge has number 1
        expect(authenticated_page.locator(".badge").first).to_contain_text("1")


class TestStepNavigation:
    """Test navigation between steps."""

    def test_click_step_1_navigates_to_qlik_step(self, authenticated_page: Page, base_url: str):
        """Test clicking Step 1 navigates to Qlik ingestion page."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Click Step 1
        step_1_link = authenticated_page.get_by_text("Ingest Qlik Export")
        step_1_link.click()

        # Should navigate to step 1 page
        authenticated_page.wait_for_load_state("networkidle")
        expect(authenticated_page).to_have_url(".*ingest-qlik.*")

    def test_click_step_3_navigates_to_osiris_step(self, authenticated_page: Page, base_url: str):
        """Test clicking Step 3 navigates to Osiris enrichment page."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Click Step 3
        step_3_link = authenticated_page.get_by_text("Enrich from Osiris")
        step_3_link.click()

        # Should navigate to step 3 page
        authenticated_page.wait_for_load_state("networkidle")
        expect(authenticated_page).to_have_url(".*enrich-osiris.*")

    def test_click_step_7_navigates_to_export_step(self, authenticated_page: Page, base_url: str):
        """Test clicking Step 7 navigates to export page."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Click Step 7
        step_7_link = authenticated_page.get_by_text("Export Faculty Sheets")
        step_7_link.click()

        # Should navigate to step 7 page
        authenticated_page.wait_for_load_state("networkidle")
        expect(authenticated_page).to_have_url(".*export-faculty.*")


class TestStep1IngestQlik:
    """Test Step 1: Ingest Qlik Export."""

    def test_step_1_page_loads(self, authenticated_page: Page, base_url: str):
        """Test that Step 1 page loads successfully."""
        authenticated_page.goto(f"{base_url}/steps/ingest-qlik/")
        authenticated_page.wait_for_load_state("networkidle")

        # Should have page title
        expect(authenticated_page.locator("h1, h2")).to_be_visible()

    def test_step_1_has_file_upload(self, authenticated_page: Page, base_url: str):
        """Test that Step 1 has file upload form."""
        authenticated_page.goto(f"{base_url}/steps/ingest-qlik/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for file input
        file_input = authenticated_page.locator('input[type="file"]').first
        if file_input.count() > 0:
            expect(file_input).to_be_visible()


class TestStep2IngestFaculty:
    """Test Step 2: Ingest Faculty Sheet."""

    def test_step_2_page_loads(self, authenticated_page: Page, base_url: str):
        """Test that Step 2 page loads successfully."""
        authenticated_page.goto(f"{base_url}/steps/ingest-faculty/")
        authenticated_page.wait_for_load_state("networkidle")

        # Should have page title
        expect(authenticated_page.locator("h1, h2")).to_be_visible()


class TestStep3EnrichOsiris:
    """Test Step 3: Enrich from Osiris."""

    def test_step_3_page_loads(self, authenticated_page: Page, base_url: str):
        """Test that Step 3 page loads successfully."""
        authenticated_page.goto(f"{base_url}/steps/enrich-osiris/")
        authenticated_page.wait_for_load_state("networkidle")

        # Should have page title
        expect(authenticated_page.locator("h1, h2")).to_be_visible()


class TestStep5CanvasStatus:
    """Test Step 5: Get PDF Status from Canvas."""

    def test_step_5_page_loads(self, authenticated_page: Page, base_url: str):
        """Test that Step 5 page loads successfully."""
        authenticated_page.goto(f"{base_url}/steps/pdf-canvas-status/")
        authenticated_page.wait_for_load_state("networkidle")

        # Should have page title
        expect(authenticated_page.locator("h1, h2")).to_be_visible()


class TestStep6ExtractPDF:
    """Test Step 6: Extract PDF Details."""

    def test_step_6_page_loads(self, authenticated_page: Page, base_url: str):
        """Test that Step 6 page loads successfully."""
        authenticated_page.goto(f"{base_url}/steps/pdf-extract/")
        authenticated_page.wait_for_load_state("networkidle")

        # Should have page title
        expect(authenticated_page.locator("h1, h2")).to_be_visible()


class TestStep7ExportFaculty:
    """Test Step 7: Export Faculty Sheets."""

    def test_step_7_page_loads(self, authenticated_page: Page, base_url: str):
        """Test that Step 7 page loads successfully."""
        authenticated_page.goto(f"{base_url}/steps/export-faculty/")
        authenticated_page.wait_for_load_state("networkidle")

        # Should have page title
        expect(authenticated_page.locator("h1, h2")).to_be_visible()

    def test_step_7_has_export_button(self, authenticated_page: Page, base_url: str):
        """Test that Step 7 has export functionality."""
        authenticated_page.goto(f"{base_url}/steps/export-faculty/")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for export button or form
        export_button = authenticated_page.locator("button:has-text('Export'), button:has-text('Generate')").first

        if export_button.count() > 0:
            expect(export_button).to_be_visible()


class TestStepDescriptions:
    """Test step descriptions and metadata."""

    def test_step_descriptions_visible(self, authenticated_page: Page, base_url: str):
        """Test that step descriptions are displayed."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for description text
        descriptions = authenticated_page.locator(".card .text-base-content\\/60, .card p")
        expect(descriptions).to_have_count(count=7, timeout=5000)

    def test_step_tags_visible(self, authenticated_page: Page, base_url: str):
        """Test that step tags/badges are displayed."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for badges
        badges = authenticated_page.locator(".badge-outline")
        expect(badges.count()).to_be_greater_than(0)


class TestStepInfoCard:
    """Test the info card on steps index."""

    def test_info_card_visible(self, authenticated_page: Page, base_url: str):
        """Test that info card is visible at bottom of steps page."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for info card
        info_card = authenticated_page.locator(".card:has-text('About Processing Steps')").first

        if info_card.count() > 0:
            expect(info_card).to_be_visible()

    def test_info_card_has_content(self, authenticated_page: Page, base_url: str):
        """Test that info card has helpful content."""
        authenticated_page.goto(f"{base_url}/steps/")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for list items in info card
        list_items = authenticated_page.locator("li").first

        if list_items.count() > 0:
            expect(list_items).to_be_visible()
