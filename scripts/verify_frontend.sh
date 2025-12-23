#!/bin/bash
# Frontend Verification Script for Easy Access Platform
# Uses curl to verify HTML content and structure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
SCREENSHOT_DIR="screenshots"
RESULTS_FILE="$SCREENSHOT_DIR/verification-results.txt"

# Test results tracking
TOTAL=0
PASSED=0
FAILED=0

# Helper functions
log_result() {
    local status="$1"
    local test_name="$2"
    local notes="$3"

    TOTAL=$((TOTAL + 1))
    if [ "$status" = "PASS" ]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓ PASS${NC}: $test_name"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗ FAIL${NC}: $test_name"
        [ -n "$notes" ] && echo "        Notes: $notes"
    fi

    echo "[$status] $test_name${notes:+ - $notes}" >> "$RESULTS_FILE"
}

check_html() {
    local url="$1"
    local selector="$2"
    local description="$3"

    local html
    html=$(curl -s "$url")

    if echo "$html" | grep -q "$selector"; then
        log_result "PASS" "$description" "Found: $selector"
        return 0
    else
        log_result "FAIL" "$description" "Not found: $selector"
        return 1
    fi
}

# Initialize
echo "========================================"
echo "Easy Access Platform Frontend Verification"
echo "Target URL: $BASE_URL"
echo "Timestamp: $(date -Iseconds)"
echo "========================================"
echo ""

mkdir -p "$SCREENSHOT_DIR"/{01-navigation,02-dashboard,03-steps-index,04-step-pages,05-ingest-system,06-admin,07-interactions,08-backend}
echo "Verification Results - $(date)" > "$RESULTS_FILE"

# Phase 1: Main Navigation
echo "=== Phase 1: Main Navigation ==="
echo ""

# Check steps index
check_html "$BASE_URL/steps/" "Processing Steps" "Steps index page title"
check_html "$BASE_URL/steps/" "badge-primary badge-lg.*1" "Step 1 badge"
check_html "$BASE_URL/steps/" "badge-primary badge-lg.*2" "Step 2 badge"
check_html "$BASE_URL/steps/" "badge-primary badge-lg.*3" "Step 3 badge"
check_html "$BASE_URL/steps/" "badge-primary badge-lg.*4" "Step 4 badge"
check_html "$BASE_URL/steps/" "badge-primary badge-lg.*5" "Step 5 badge"
check_html "$BASE_URL/steps/" "badge-primary badge-lg.*6" "Step 6 badge"
check_html "$BASE_URL/steps/" "badge-primary badge-lg.*7" "Step 7 badge"
check_html "$BASE_URL/steps/" "Ingest Qlik Export" "Step 1 title"
check_html "$BASE_URL/steps/" "Ingest Faculty Sheet" "Step 2 title"
check_html "$BASE_URL/steps/" "Enrich from Osiris" "Step 3 title"
check_html "$BASE_URL/steps/" "Enrich from People Pages" "Step 4 title"
check_html "$BASE_URL/steps/" "Get PDF Status from Canvas" "Step 5 title"
check_html "$BASE_URL/steps/" "Extract PDF Details" "Step 6 title"
check_html "$BASE_URL/steps/" "Export Faculty Sheets" "Step 7 title"
check_html "$BASE_URL/steps/" "Copyright Compliance Platform" "Copyright Platform subtitle"

# Save HTML for manual inspection
curl -s "$BASE_URL/steps/" > "$SCREENSHOT_DIR/01-navigation/steps-index.html"

echo ""

# Phase 2: Dashboard
echo "=== Phase 2: Dashboard ==="
echo ""

check_html "$BASE_URL/" "Copyright Dashboard" "Dashboard page title"
check_html "$BASE_URL/" "Enrich All" "Enrich All button"
check_html "$BASE_URL/" "Download Faculty Sheets" "Download button"
check_html "$BASE_URL/" "Upload Excel" "Upload button"
check_html "$BASE_URL/" "data-grid" "Data grid container"

curl -s "$BASE_URL/" > "$SCREENSHOT_DIR/02-dashboard/dashboard.html"

echo ""

# Phase 3: Step Pages
echo "=== Phase 3: Step Pages ==="
echo ""

check_html "$BASE_URL/steps/ingest-qlik/" "Ingest Qlik Export" "Step 1 page title"
check_html "$BASE_URL/steps/ingest-qlik/" "breadcrumbs" "Breadcrumbs"
check_html "$BASE_URL/steps/ingest-qlik/" "Back to Steps" "Back to Steps button"
check_html "$BASE_URL/steps/ingest-qlik/" "Input Selection" "Input Selection card"
check_html "$BASE_URL/steps/ingest-qlik/" "Settings" "Settings card"
check_html "$BASE_URL/steps/ingest-qlik/" "Progress" "Progress card"

curl -s "$BASE_URL/steps/ingest-qlik/" > "$SCREENSHOT_DIR/04-step-pages/step-01-ingest-qlik.html"

check_html "$BASE_URL/steps/enrich-osiris/" "Enrich from Osiris" "Step 3 page title"
check_html "$BASE_URL/steps/enrich-osiris/" "Enrich all items" "Enrich all items radio"
check_html "$BASE_URL/steps/enrich-osiris/" "Select specific items" "Select specific items radio"
check_html "$BASE_URL/steps/enrich-osiris/" "Material ID" "Items table column"

curl -s "$BASE_URL/steps/enrich-osiris/" > "$SCREENSHOT_DIR/04-step-pages/step-03-enrich-osiris.html"

check_html "$BASE_URL/steps/pdf-canvas-status/" "Get PDF Status from Canvas" "Step 5 page title"
curl -s "$BASE_URL/steps/pdf-canvas-status/" > "$SCREENSHOT_DIR/04-step-pages/step-05-pdf-canvas-status.html"

check_html "$BASE_URL/steps/export-faculty/" "Export Faculty Sheets" "Step 7 page title"
curl -s "$BASE_URL/steps/export-faculty/" > "$SCREENSHOT_DIR/04-step-pages/step-07-export-faculty.html"

echo ""

# Phase 4: Ingest System
echo "=== Phase 4: Ingest System ==="
echo ""

check_html "$BASE_URL/ingest/" "Total Batches" "Total Batches stat"
check_html "$BASE_URL/ingest/" "Pending" "Pending stat"
check_html "$BASE_URL/ingest/" "Processing" "Processing stat"
check_html "$BASE_URL/ingest/" "Completed" "Completed stat"
check_html "$BASE_URL/ingest/" "Failed" "Failed stat"
check_html "$BASE_URL/ingest/" "Quick Actions" "Quick Actions card"
check_html "$BASE_URL/ingest/" "Recent Batches" "Recent Batches section"

curl -s "$BASE_URL/ingest/" > "$SCREENSHOT_DIR/05-ingest-system/ingest-dashboard.html"

echo ""

# Phase 5: UT Branding
echo "=== Phase 5: UT Branding ==="
echo ""

check_html "$BASE_URL/" "ut-navbar" "UT navbar class"
check_html "$BASE_URL/" "btn-ut" "UT button class"
check_html "$BASE_URL/" "University of Twente" "University of Twente text"
check_html "$BASE_URL/steps/" "ut-card\|card bg-base-100" "UT card styling"

echo ""

# Phase 6: Login Page
echo "=== Phase 6: Login Page ==="
echo ""

check_html "$BASE_URL/accounts/login/" "login\|Login\|Sign in" "Login page"

curl -s "$BASE_URL/accounts/login/" > "$SCREENSHOT_DIR/06-admin/login-page.html"

echo ""

# Phase 7: HTMX Attributes
echo "=== Phase 7: HTMX Attributes ==="
echo ""

# Check for HTMX script loading
DASHBOARD_HTML=$(curl -s "$BASE_URL/")
if echo "$DASHBOARD_HTML" | grep -q "hx-"; then
    log_result "PASS" "HTMX attributes present" "Found hx- attributes"
else
    log_result "FAIL" "HTMX attributes present" "No hx- attributes found"
fi

# Check for HTMX script
if echo "$DASHBOARD_HTML" | grep -q "htmx.org"; then
    log_result "PASS" "HTMX script loaded" "Found htmx.org script"
else
    log_result "FAIL" "HTMX script loaded" "HTMX script not found"
fi

echo ""

# Phase 8: Alpine.js Components
echo "=== Phase 8: Alpine.js Components ==="
echo ""

if echo "$DASHBOARD_HTML" | grep -q "x-data"; then
    log_result "PASS" "Alpine.js directives present" "Found x-data attributes"
else
    log_result "FAIL" "Alpine.js directives present" "No x-data attributes found"
fi

if echo "$DASHBOARD_HTML" | grep -q "alpinejs"; then
    log_result "PASS" "Alpine.js script loaded" "Found alpinejs script"
else
    log_result "FAIL" "Alpine.js script loaded" "Alpine.js script not found"
fi

echo ""

# Phase 9: DaisyUI Styling
echo "=== Phase 9: DaisyUI Styling ==="
echo ""

if echo "$DASHBOARD_HTML" | grep -q "daisyui"; then
    log_result "PASS" "DaisyUI CSS loaded" "Found daisyui CSS"
else
    log_result "FAIL" "DaisyUI CSS loaded" "DaisyUI CSS not found"
fi

if echo "$DASHBOARD_HTML" | grep -q "data-theme"; then
    log_result "PASS" "DaisyUI theme set" "Found data-theme attribute"
else
    log_result "FAIL" "DaisyUI theme set" "data-theme attribute not found"
fi

echo ""

# Summary
echo "========================================"
echo "Verification Complete"
echo "========================================"
echo ""
echo "Total Tests: $TOTAL"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Check results above.${NC}"
    exit 1
fi
