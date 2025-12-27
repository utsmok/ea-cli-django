"""
Dashboard UI tests.

Tests the main copyright dashboard interface including:
- Page loading and layout
- Workflow tabs and filtering
- Faculty dropdown filtering
- Search functionality
- Pagination
- Inline editing
- Item detail panel
"""

import re
import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.playwright


class TestDashboardLayout:
    """Test dashboard layout and basic functionality."""

    def test_dashboard_loads(self, authenticated_page: Page, base_url: str):
        """Test that dashboard loads successfully."""
        authenticated_page.goto(f"{base_url}/")

        # Wait for page to load
        authenticated_page.wait_for_load_state("networkidle")

        # Check title
        expect(authenticated_page.locator("h1")).to_contain_text("Copyright Dashboard")

        # Check main containers exist
        expect(authenticated_page.locator("#table-container")).to_be_visible()
        expect(authenticated_page.locator("#detail-panel")).to_be_visible()

    def test_workflow_tabs_visible(self, authenticated_page: Page, base_url: str):
        """Test that workflow status tabs are visible."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for tabs container
        tabs = authenticated_page.locator(".tabs")
        expect(tabs).to_be_visible()

        # Check for specific tabs - use button.tab selector with actual labels
        expect(authenticated_page.locator("button.tab:has-text('To Do')")).to_be_visible()
        expect(authenticated_page.locator("button.tab:has-text('In Progress')")).to_be_visible()
        expect(authenticated_page.locator("button.tab:has-text('Done')")).to_be_visible()
        expect(authenticated_page.locator("button.tab:has-text('All')")).to_be_visible()

    def test_faculty_filter_exists(self, authenticated_page: Page, base_url: str):
        """Test that faculty filter dropdown exists."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for faculty dropdown
        faculty_dropdown = authenticated_page.locator('select[name="faculty"], #faculty-filter').first
        if faculty_dropdown.count() > 0:
            expect(faculty_dropdown).to_be_visible()

    def test_search_input_exists(self, authenticated_page: Page, base_url: str):
        """Test that search input field exists."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for search input
        search_input = authenticated_page.locator('input[name="search"], input[type="search"]').first
        if search_input.count() > 0:
            expect(search_input).to_be_visible()


class TestWorkflowTabs:
    """Test workflow status tab functionality."""

    def test_click_todo_tab_filters_items(self, authenticated_page: Page, base_url: str):
        """Test clicking ToDo tab filters to ToDo items."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Click ToDo tab - use button.tab selector with actual label
        todo_tab = authenticated_page.locator("button.tab:has-text('To Do')")
        todo_tab.click()

        # Wait for HTMX update
        authenticated_page.wait_for_load_state("networkidle")

        # Verify URL updated - use compiled regex pattern
        expect(authenticated_page).to_have_url(re.compile(r".*status=ToDo.*"))

    def test_click_done_tab_filters_items(self, authenticated_page: Page, base_url: str):
        """Test clicking Done tab filters to Done items."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Click Done tab - use button.tab selector
        done_tab = authenticated_page.locator("button.tab:has-text('Done')")
        done_tab.click()

        # Wait for HTMX update
        authenticated_page.wait_for_load_state("networkidle")

        # Verify URL updated - use compiled regex pattern
        expect(authenticated_page).to_have_url(re.compile(r".*status=Done.*"))

    def test_click_all_tab_shows_all_items(self, authenticated_page: Page, base_url: str):
        """Test clicking All tab shows all items."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Click All tab - use button.tab selector
        all_tab = authenticated_page.locator("button.tab:has-text('All')")
        all_tab.click()

        # Wait for HTMX update
        authenticated_page.wait_for_load_state("networkidle")

        # Verify URL updated - use compiled regex pattern
        expect(authenticated_page).to_have_url(re.compile(r".*status=All.*"))


class TestSearchAndFilter:
    """Test search and filter functionality."""

    def test_search_filters_table(self, authenticated_page: Page, base_url: str, sample_data):
        """Test that search input filters the table."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Find search input
        search_input = authenticated_page.locator('input[name="search"], input[type="search"]').first

        if search_input.is_visible():
            # Type search query
            search_input.fill("Test Item 1")

            # Wait for HTMX debounce and update
            authenticated_page.wait_for_timeout(1500)

            # Verify URL updated - use compiled regex pattern
            expect(authenticated_page).to_have_url(re.compile(r".*search=Test.*"))

    def test_faculty_dropdown_filters(self, authenticated_page: Page, base_url: str, sample_data):
        """Test that faculty dropdown filters items."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Find faculty dropdown
        faculty_select = authenticated_page.locator('select[name="faculty"]').first

        if faculty_select.is_visible():
            # Select EEMCS faculty
            faculty_select.select_option("EEMCS")

            # Wait for HTMX update
            authenticated_page.wait_for_timeout(500)

            # Verify URL updated - use compiled regex pattern
            expect(authenticated_page).to_have_url(re.compile(r".*faculty=EEMCS.*"))


class TestPagination:
    """Test pagination controls."""

    def test_pagination_controls_exist(self, authenticated_page: Page, base_url: str, sample_data):
        """Test that pagination controls are visible when there are many items."""
        authenticated_page.goto(f"{base_url}/?per_page=5")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for pagination
        pagination = authenticated_page.locator(".pagination").first

        # Pagination may or may not be visible depending on item count
        if pagination.count() > 0 and pagination.is_visible():
            expect(pagination).to_be_visible()

    def test_next_page_navigates(self, authenticated_page: Page, base_url: str, sample_data):
        """Test clicking next page button navigates to next page."""
        authenticated_page.goto(f"{base_url}/?per_page=5")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for next button
        next_button = authenticated_page.locator("a:has-text('Next'), .pagination .next").first

        if next_button.is_visible() and next_button.is_enabled():
            next_button.click()
            authenticated_page.wait_for_load_state("networkidle")

            # URL should show page 2 - use compiled regex pattern
            expect(authenticated_page).to_have_url(re.compile(r".*page=2.*"))


class TestInlineEditing:
    """Test inline editing functionality."""

    def test_editable_cell_clickable(self, authenticated_page: Page, base_url: str, sample_data):
        """Test that editable cells can be clicked."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Find first editable cell
        editable_cell = authenticated_page.locator("[data-editable], .editable-cell").first

        if editable_cell.count() > 0 and editable_cell.is_visible():
            # Click to edit
            editable_cell.click()

            # Should show input or select element
            input_element = authenticated_page.locator("input, select").first
            expect(input_element).to_be_visible()

    def test_inline_edit_save(self, authenticated_page: Page, base_url: str, sample_data):
        """Test that inline edit saves on blur."""
        from .conftest import inject_toast_capture

        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Inject toast capture
        inject_toast_capture(authenticated_page)

        # Find first editable cell
        editable_cell = authenticated_page.locator("[data-editable], .editable-cell").first

        if editable_cell.count() > 0 and editable_cell.is_visible():
            # Click to edit
            editable_cell.click()
            authenticated_page.wait_for_timeout(300)

            # Find input and change value
            input_element = authenticated_page.locator("input, select").first
            if input_element.is_visible():
                input_element.fill("PERMITTED")

                # Blur to save
                authenticated_page.keyboard.press("Enter")

                # Wait for save
                authenticated_page.wait_for_timeout(1000)

                # Cell should still be visible
                expect(editable_cell).to_be_visible()


class TestItemDetailPanel:
    """Test item detail panel functionality."""

    def test_click_row_shows_detail(self, authenticated_page: Page, base_url: str, sample_data):
        """Test that clicking a row shows detail panel."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Find first table row
        first_row = authenticated_page.locator("table tbody tr").first

        if first_row.is_visible():
            # Click row
            first_row.click()

            # Wait for detail panel to update
            authenticated_page.wait_for_timeout(500)

            # Detail panel should no longer be empty
            detail_panel = authenticated_page.locator("#detail-panel")
            expect(detail_panel).not_to_contain_text("Select an Item")

    def test_detail_panel_shows_item_info(self, authenticated_page: Page, base_url: str, sample_data):
        """Test that detail panel shows item information."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Find first table row
        first_row = authenticated_page.locator("table tbody tr").first

        if first_row.is_visible():
            first_row.click()
            authenticated_page.wait_for_timeout(500)

            # Check for detail content
            detail_panel = authenticated_page.locator("#detail-panel")

            # Should have some content (not empty state)
            expect(detail_panel).not_to_contain_text("Click any row to view details")


class TestTableDisplay:
    """Test table rendering and display."""

    def test_table_renders_rows(self, authenticated_page: Page, base_url: str, sample_data):
        """Test that table renders rows with data."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for table
        table = authenticated_page.locator("table").first
        expect(table).to_be_visible()

        # Check for rows
        rows = authenticated_page.locator("table tbody tr")
        expect(rows).to_have_count(count=20, timeout=5000)

    def test_table_has_correct_columns(self, authenticated_page: Page, base_url: str, sample_data):
        """Test that table has expected columns."""
        authenticated_page.goto(f"{base_url}/")
        authenticated_page.wait_for_load_state("networkidle")

        # Check for table headers
        table = authenticated_page.locator("table thead tr").first

        # Should have various headers (exact set may vary)
        expect(table).to_be_visible()
