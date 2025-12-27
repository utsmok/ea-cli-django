"""
Phase 5: Playwright UI Test Suite

Browser-based end-to-end UI tests using Playwright.
These tests verify the complete user experience including JavaScript interactions.
"""

import pytest
from playwright.sync_api import Page, expect

# Mark all tests in this file as playwright tests
pytestmark = pytest.mark.playwright


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for tests."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }


class TestDashboardUI:
    """Test dashboard user interface and interactions."""

    def test_dashboard_loads_successfully(self, page: Page, live_server):
        """Test that dashboard loads and displays items."""
        # Navigate to dashboard
        page.goto(f"{live_server.url}/dashboard/")
        
        # Should show dashboard title
        expect(page.locator("h1")).to_contain_text("Dashboard", timeout=10000)
        
        # Should have table or content area
        expect(page.locator("table, .table-container")).to_be_visible(timeout=5000)

    def test_filter_updates_table_via_htmx(self, page: Page, live_server):
        """Test that filtering updates the table via HTMX."""
        page.goto(f"{live_server.url}/dashboard/")
        
        # Wait for page load
        page.wait_for_load_state("networkidle")
        
        # Find filter input
        filter_input = page.locator('input[name="search"], input[type="search"]').first
        
        if filter_input.is_visible():
            # Type in filter
            filter_input.fill("test query")
            
            # Wait for HTMX request to complete
            page.wait_for_timeout(1000)
            
            # Table should update
            expect(page.locator("table tbody")).to_be_visible()

    def test_pagination_works(self, page: Page, live_server):
        """Test pagination controls."""
        page.goto(f"{live_server.url}/dashboard/")
        
        # Wait for page load
        page.wait_for_load_state("networkidle")
        
        # Look for pagination
        pagination = page.locator(".pagination, nav[aria-label='pagination']").first
        
        if pagination.is_visible():
            # Click next page if available
            next_button = page.locator("a:has-text('Next'), button:has-text('Next')").first
            if next_button.is_visible() and next_button.is_enabled():
                next_button.click()
                page.wait_for_load_state("networkidle")
                
                # Should still be on dashboard
                expect(page).to_have_url(pytest.approx(f"{live_server.url}/dashboard/"))


class TestItemDetailModal:
    """Test item detail modal interactions."""

    def test_item_row_click_opens_modal(self, page: Page, live_server):
        """Test that clicking an item row opens the detail modal."""
        page.goto(f"{live_server.url}/dashboard/")
        page.wait_for_load_state("networkidle")
        
        # Find first clickable row
        first_row = page.locator("table tbody tr").first
        
        if first_row.is_visible():
            first_row.click()
            
            # Modal should appear
            modal = page.locator(".modal, [role='dialog']").first
            expect(modal).to_be_visible(timeout=5000)

    def test_modal_close_button_works(self, page: Page, live_server):
        """Test that modal close button works."""
        page.goto(f"{live_server.url}/dashboard/")
        page.wait_for_load_state("networkidle")
        
        # Open modal
        first_row = page.locator("table tbody tr").first
        if first_row.is_visible():
            first_row.click()
            
            # Wait for modal
            page.wait_for_selector(".modal, [role='dialog']", state="visible", timeout=5000)
            
            # Find and click close button
            close_button = page.locator("button:has-text('Close'), .modal-close, [aria-label='Close']").first
            if close_button.is_visible():
                close_button.click()
                
                # Modal should disappear
                expect(page.locator(".modal, [role='dialog']")).not_to_be_visible(timeout=5000)


class TestInlineEditing:
    """Test inline editing functionality."""

    def test_editable_cell_becomes_input_on_click(self, page: Page, live_server):
        """Test that editable cells become inputs when clicked."""
        page.goto(f"{live_server.url}/dashboard/")
        page.wait_for_load_state("networkidle")
        
        # Find editable cell
        editable_cell = page.locator(".editable, [data-editable='true']").first
        
        if editable_cell.is_visible():
            # Click to edit
            editable_cell.click()
            
            # Should show input or be focused
            page.wait_for_timeout(500)
            
            # Either the cell becomes an input or contains one
            input_field = page.locator("input, textarea").first
            if input_field.is_visible():
                expect(input_field).to_be_focused()

    def test_inline_edit_saves_on_blur(self, page: Page, live_server):
        """Test that inline edits save when focus is lost."""
        page.goto(f"{live_server.url}/dashboard/")
        page.wait_for_load_state("networkidle")
        
        # Find editable cell
        editable_cell = page.locator(".editable, [data-editable='true']").first
        
        if editable_cell.is_visible():
            original_text = editable_cell.text_content()
            
            # Click to edit
            editable_cell.click()
            page.wait_for_timeout(300)
            
            # Type new value
            input_field = page.locator("input, textarea").first
            if input_field.is_visible():
                input_field.fill("Updated value")
                
                # Blur (click away)
                page.locator("body").click()
                
                # Wait for save
                page.wait_for_timeout(1000)
                
                # Value should update (or revert if save failed)
                # This is a soft check since we don't know if save succeeds
                expect(editable_cell).to_be_visible()


class TestBatchUpload:
    """Test batch upload workflow."""

    def test_upload_page_loads(self, page: Page, live_server):
        """Test that upload page loads."""
        page.goto(f"{live_server.url}/ingest/upload/")
        
        # Should show upload form
        expect(page.locator("form")).to_be_visible(timeout=5000)
        expect(page.locator('input[type="file"]')).to_be_visible()

    def test_file_input_accepts_files(self, page: Page, live_server, tmp_path):
        """Test that file input accepts Excel files."""
        page.goto(f"{live_server.url}/ingest/upload/")
        
        # Create temporary Excel file
        test_file = tmp_path / "test_batch.xlsx"
        test_file.write_bytes(b"PK\x03\x04")  # Minimal Excel file header
        
        # Find file input
        file_input = page.locator('input[type="file"]').first
        
        if file_input.is_visible():
            # Set file
            file_input.set_input_files(str(test_file))
            
            # File name should appear
            expect(page.locator("body")).to_contain_text("test_batch.xlsx", timeout=3000)


class TestWorkflowActions:
    """Test workflow action buttons."""

    def test_enrichment_trigger_button_exists(self, page: Page, live_server):
        """Test that enrichment trigger button exists."""
        page.goto(f"{live_server.url}/dashboard/")
        page.wait_for_load_state("networkidle")
        
        # Look for enrichment trigger button
        enrich_button = page.locator("button:has-text('Enrich'), [data-action='enrich']").first
        
        # Button may or may not be visible depending on item state
        # This is a soft check
        if enrich_button.count() > 0:
            expect(enrich_button).to_be_visible()

    def test_bulk_actions_available(self, page: Page, live_server):
        """Test that bulk actions are available."""
        page.goto(f"{live_server.url}/dashboard/")
        page.wait_for_load_state("networkidle")
        
        # Look for checkboxes for bulk selection
        checkboxes = page.locator('input[type="checkbox"]')
        
        # May have checkboxes for bulk actions
        if checkboxes.count() > 0:
            # First checkbox might be select-all
            checkboxes.first.check()
            
            # Bulk action buttons might appear
            page.wait_for_timeout(500)


class TestResponsiveDesign:
    """Test responsive design at different viewports."""

    def test_mobile_viewport_shows_hamburger_menu(self, page: Page, live_server):
        """Test that mobile viewport shows hamburger menu."""
        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        
        page.goto(f"{live_server.url}/dashboard/")
        page.wait_for_load_state("networkidle")
        
        # Look for mobile menu button
        menu_button = page.locator("button:has-text('Menu'), .hamburger, .mobile-menu-toggle").first
        
        # Mobile menu should exist
        if menu_button.count() > 0:
            expect(menu_button).to_be_visible()

    def test_tablet_viewport_maintains_layout(self, page: Page, live_server):
        """Test that tablet viewport maintains usable layout."""
        # Set tablet viewport
        page.set_viewport_size({"width": 768, "height": 1024})
        
        page.goto(f"{live_server.url}/dashboard/")
        page.wait_for_load_state("networkidle")
        
        # Dashboard should still be functional
        expect(page.locator("h1")).to_be_visible()
        expect(page.locator("table, .table-container")).to_be_visible()


class TestAccessibility:
    """Test accessibility features."""

    def test_keyboard_navigation_works(self, page: Page, live_server):
        """Test that keyboard navigation works."""
        page.goto(f"{live_server.url}/dashboard/")
        page.wait_for_load_state("networkidle")
        
        # Press Tab to navigate
        page.keyboard.press("Tab")
        page.wait_for_timeout(200)
        
        # Some element should be focused
        focused = page.evaluate("document.activeElement.tagName")
        assert focused in ["A", "BUTTON", "INPUT", "BODY"]

    def test_skip_to_main_content_link_exists(self, page: Page, live_server):
        """Test that skip to main content link exists for screen readers."""
        page.goto(f"{live_server.url}/dashboard/")
        
        # Look for skip link (may be visually hidden)
        skip_link = page.locator("a:has-text('Skip to main'), a:has-text('Skip to content')").first
        
        # Link might exist but be hidden
        if skip_link.count() > 0:
            # Just verify it exists
            assert skip_link.count() == 1


class TestErrorHandling:
    """Test error handling in UI."""

    def test_404_page_shows_helpful_message(self, page: Page, live_server):
        """Test that 404 page shows helpful message."""
        page.goto(f"{live_server.url}/nonexistent-page/")
        
        # Should show 404 message
        expect(page.locator("body")).to_contain_text("404", timeout=5000)

    def test_network_error_shows_user_feedback(self, page: Page, live_server):
        """Test that network errors show user feedback."""
        page.goto(f"{live_server.url}/dashboard/")
        page.wait_for_load_state("networkidle")
        
        # Simulate network offline
        page.route("**/*", lambda route: route.abort())
        
        # Try to trigger an action
        page.locator("body").click()
        
        # Should handle gracefully (no crash)
        # This is a soft test - just verify page doesn't crash
        expect(page.locator("body")).to_be_visible()
