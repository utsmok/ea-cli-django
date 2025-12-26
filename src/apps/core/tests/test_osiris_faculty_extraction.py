"""
Tests for faculty extraction from people.utwente.nl profile pages.
"""

import bs4

from apps.core.services.osiris import FACULTY_ABBREVS, _parse_person_page


class TestFacultyConstants:
    """Test faculty abbreviation constants."""

    def test_faculty_abbrevs_defined(self):
        """Test that FACULTY_ABBREVS is properly defined."""
        assert isinstance(FACULTY_ABBREVS, list)
        assert len(FACULTY_ABBREVS) == 5
        assert "BMS" in FACULTY_ABBREVS
        assert "ET" in FACULTY_ABBREVS
        assert "EEMCS" in FACULTY_ABBREVS
        assert "ITC" in FACULTY_ABBREVS
        assert "TNW" in FACULTY_ABBREVS


class TestParsePersonPageFacultyExtraction:
    """Test _parse_person_page function for faculty extraction."""

    def test_extracts_main_name_from_h1(self):
        """Test extraction of main_name from H1 header."""
        html = """
        <html>
            <body><h1>Dr. Jane Doe</h1></body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/jane-doe", "Jane Doe"
        )

        assert result["main_name"] == "Dr. Jane Doe"

    def test_extracts_email_from_mailto_link(self):
        """Test extraction of email from mailto link."""
        html = """
        <html>
            <body>
                <h1>Dr. Jane Doe</h1>
                <a href="mailto:j.doe@utwente.nl">j.doe@utwente.nl</a>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/jane-doe", "Jane Doe"
        )

        assert result["email"] == "j.doe@utwente.nl"

    def test_extracts_faculty_from_org_widget(self):
        """Test extraction of faculty from organization widget."""
        html = """
        <html>
            <body>
                <h1>Dr. Jane Doe</h1>
                <div class="widget-linklist--smallicons">
                    <div class="widget-linklist__text">Faculty of Electrical Engineering (ET)</div>
                    <div class="widget-linklist__text">Department of X (DEPT-X)</div>
                </div>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/jane-doe", "Jane Doe"
        )

        assert result["faculty_abbrev"] == "ET"
        assert result["faculty_name"] == "Faculty of Electrical Engineering"

    def test_extracts_tnw_faculty(self):
        """Test extraction of TNW faculty."""
        html = """
        <html>
            <body>
                <h1>Dr. John Smith</h1>
                <div class="widget-linklist--smallicons">
                    <div class="widget-linklist__text">Faculty of Science and Technology (TNW)</div>
                </div>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/john-smith", "John Smith"
        )

        assert result["faculty_abbrev"] == "TNW"
        assert result["faculty_name"] == "Faculty of Science and Technology"

    def test_extracts_eemcs_faculty(self):
        """Test extraction of EEMCS faculty."""
        html = """
        <html>
            <body>
                <h1>Dr. Alice Johnson</h1>
                <div class="widget-linklist--smallicons">
                    <div class="widget-linklist__text">Faculty of Engineering Technology (EEMCS)</div>
                </div>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/alice-johnson", "Alice Johnson"
        )

        assert result["faculty_abbrev"] == "EEMCS"
        assert result["faculty_name"] == "Faculty of Engineering Technology"

    def test_extracts_bms_faculty(self):
        """Test extraction of BMS faculty."""
        html = """
        <html>
            <body>
                <h1>Dr. Bob Brown</h1>
                <div class="widget-linklist--smallicons">
                    <div class="widget-linklist__text">Faculty of Behavioural Sciences (BMS)</div>
                </div>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/bob-brown", "Bob Brown"
        )

        assert result["faculty_abbrev"] == "BMS"
        assert result["faculty_name"] == "Faculty of Behavioural Sciences"

    def test_extracts_itc_faculty(self):
        """Test extraction of ITC faculty."""
        html = """
        <html>
            <body>
                <h1>Dr. Carol White</h1>
                <div class="widget-linklist--smallicons">
                    <div class="widget-linklist__text">Faculty of Geo-Information Science (ITC)</div>
                </div>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/carol-white", "Carol White"
        )

        assert result["faculty_abbrev"] == "ITC"
        assert result["faculty_name"] == "Faculty of Geo-Information Science"

    def test_no_faculty_when_no_org_widget(self):
        """Test that faculty_abbrev is None when no org widget exists."""
        html = """
        <html>
            <body>
                <h1>Dr. No Faculty</h1>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/no-faculty", "No Faculty"
        )

        assert result["faculty_abbrev"] is None
        assert result["faculty_name"] is None

    def test_non_faculty_org_not_extracted(self):
        """Test that non-faculty organizations are not extracted as faculty."""
        html = """
        <html>
            <body>
                <h1>Dr. Department Only</h1>
                <div class="widget-linklist--smallicons">
                    <div class="widget-linklist__text">Department of Computer Science (CS)</div>
                </div>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/dept-only", "Department Only"
        )

        # CS is not in FACULTY_ABBREVS, so faculty_abbrev should be None
        assert result["faculty_abbrev"] is None

    def test_malformed_org_text_handled_gracefully(self):
        """Test that malformed org text doesn't cause errors."""
        html = """
        <html>
            <body>
                <h1>Dr. Malformed</h1>
                <div class="widget-linklist--smallicons">
                    <div class="widget-linklist__text">Missing parentheses</div>
                    <div class="widget-linklist__text">Empty ()</div>
                </div>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/malformed", "Malformed"
        )

        # Should not raise an exception and return None for faculty
        assert result["faculty_abbrev"] is None

    def test_first_faculty_used_when_multiple(self):
        """Test that first faculty is used when multiple exist."""
        html = """
        <html>
            <body>
                <h1>Dr. Multi Faculty</h1>
                <div class="widget-linklist--smallicons">
                    <div class="widget-linklist__text">Faculty of Electrical Engineering (ET)</div>
                    <div class="widget-linklist__text">Faculty of Science (TNW)</div>
                </div>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/multi", "Multi Faculty"
        )

        # Should use the first faculty found
        assert result["faculty_abbrev"] == "ET"

    def test_returns_all_expected_fields(self):
        """Test that all expected fields are present in result."""
        html = """
        <html>
            <body>
                <h1>Dr. Complete</h1>
                <a href="mailto:complete@utwente.nl">complete@utwente.nl</a>
                <div class="widget-linklist--smallicons">
                    <div class="widget-linklist__text">Faculty of Engineering Technology (EEMCS)</div>
                </div>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        result = _parse_person_page(
            soup, "https://people.utwente.nl/complete", "Complete"
        )

        expected_keys = {
            "input_name",
            "people_page_url",
            "main_name",
            "email",
            "faculty_abbrev",
            "faculty_name",
        }
        assert set(result.keys()) == expected_keys
        assert result["input_name"] == "Complete"
        assert result["people_page_url"] == "https://people.utwente.nl/complete"
