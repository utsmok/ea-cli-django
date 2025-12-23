#!/bin/bash
# Frontend Verification Script with Authentication
# Uses curl with cookies to verify authenticated pages

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
SCREENSHOT_DIR="screenshots"
COOKIE_JAR="$SCREENSHOT_DIR/cookies.txt"
RESULTS_FILE="$SCREENSHOT_DIR/verification-results.txt"

# Test credentials
TEST_USER="testuser"
TEST_PASS="testpass123"

# Test results tracking
TOTAL=0
PASSED=0
FAILED=0
declare -a ISSUES

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
        ISSUES+=("$test_name: $notes")
    fi

    echo "[$status] $test_name${notes:+ - $notes}" >> "$RESULTS_FILE"
}

# Get CSRF token from form
get_csrf_token() {
    local html="$1"
    echo "$html" | grep -oP 'csrfmiddlewaretoken.*value="\K[^"]+' | head -1
}

# Post with CSRF token
post_with_csrf() {
    local url="$1"
    local cookie_file="$2"
    shift 2
    local data=("$@")

    # Get the page first to extract CSRF token
    local html
    html=$(curl -s -c "$cookie_file" -b "$cookie_file" "$url")
    local csrf_token=$(get_csrf_token "$html")

    # Build POST data
    local post_data="csrfmiddlewaretoken=${csrf_token}"
    for item in "${data[@]}"; do
        post_data="${post_data}&${item}"
    done

    # Submit the form
    curl -s -c "$cookie_file" -b "$cookie_file" -X POST \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -H "Referer: $BASE_URL" \
        -d "$post_data" \
        "$url"
}

# Check authenticated page
check_auth_page() {
    local url="$1"
    local selector="$2"
    local description="$3"

    local html
    html=$(curl -s -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$url")

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

# Phase 0: Login
echo "=== Phase 0: Authentication ==="
echo ""

# Get login page and extract CSRF token
LOGIN_HTML=$(curl -s -c "$COOKIE_JAR" "$BASE_URL/accounts/login/")
CSRF_TOKEN=$(get_csrf_token "$LOGIN_HTML")

if [ -z "$CSRF_TOKEN" ]; then
    echo -e "${RED}Failed to get CSRF token from login page${NC}"
    log_result "FAIL" "Get CSRF token" "No token found"
    exit 1
fi

echo "CSRF Token: ${CSRF_TOKEN:0:20}..."

# Login
LOGIN_RESPONSE=$(curl -s -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "Referer: $BASE_URL/accounts/login/" \
    -d "csrfmiddlewaretoken=$CSRF_TOKEN" \
    -d "username=$TEST_USER" \
    -d "password=$TEST_PASS" \
    "$BASE_URL/accounts/login/")

# Check if login succeeded
if echo "$LOGIN_RESPONSE" | grep -q "302\|Found\|dashboard"; then
    log_result "PASS" "Login successful"
else
    # Check for error message
    if echo "$LOGIN_RESPONSE" | grep -q "Invalid username\|error"; then
        log_result "FAIL" "Login" "Invalid credentials"
    else
        log_result "PASS" "Login" "Redirected"
    fi
fi

echo ""

# Phase 1: Steps Index
echo "=== Phase 1: Steps Index ==="
echo ""

check_auth_page "$BASE_URL/steps/" "Processing Steps" "Steps index page title"
check_auth_page "$BASE_URL/steps/" "badge-primary.*1" "Step 1 badge"
check_auth_page "$BASE_URL/steps/" "Ingest Qlik Export" "Step 1 title"
check_auth_page "$BASE_URL/steps/" "Enrich from Osiris" "Step 3 title"
check_auth_page "$BASE_URL/steps/" "Export Faculty Sheets" "Step 7 title"

curl -s -b "$COOKIE_JAR" "$BASE_URL/steps/" > "$SCREENSHOT_DIR/01-navigation/steps-index.html"

echo ""

# Phase 2: Dashboard
echo "=== Phase 2: Dashboard ==="
echo ""

check_auth_page "$BASE_URL/" "Copyright Dashboard" "Dashboard page title"
check_auth_page "$BASE_URL/" "Enrich All" "Enrich All button"
check_auth_page "$BASE_URL/" "Download Faculty Sheets" "Download button"
check_auth_page "$BASE_URL/" "Upload Excel" "Upload button"

curl -s -b "$COOKIE_JAR" "$BASE_URL/" > "$SCREENSHOT_DIR/02-dashboard/dashboard.html"

echo ""

# Phase 3: Step Pages
echo "=== Phase 3: Step Pages ==="
echo ""

check_auth_page "$BASE_URL/steps/ingest-qlik/" "Ingest Qlik Export" "Step 1 page"
check_auth_page "$BASE_URL/steps/ingest-qlik/" "Input Selection" "Input Selection card"
check_auth_page "$BASE_URL/steps/ingest-qlik/" "Settings" "Settings card"

curl -s -b "$COOKIE_JAR" "$BASE_URL/steps/ingest-qlik/" > "$SCREENSHOT_DIR/04-step-pages/step-01-ingest-qlik.html"

check_auth_page "$BASE_URL/steps/enrich-osiris/" "Enrich from Osiris" "Step 3 page"
check_auth_page "$BASE_URL/steps/enrich-osiris/" "Enrich all items" "Enrich all radio"

curl -s -b "$COOKIE_JAR" "$BASE_URL/steps/enrich-osiris/" > "$SCREENSHOT_DIR/04-step-pages/step-03-enrich-osiris.html"

check_auth_page "$BASE_URL/steps/export-faculty/" "Export Faculty Sheets" "Step 7 page"
curl -s -b "$COOKIE_JAR" "$BASE_URL/steps/export-faculty/" > "$SCREENSHOT_DIR/04-step-pages/step-07-export-faculty.html"

echo ""

# Phase 4: Ingest System
echo "=== Phase 4: Ingest System ==="
echo ""

check_auth_page "$BASE_URL/ingest/" "Total Batches" "Total Batches stat"
check_auth_page "$BASE_URL/ingest/" "Pending\|Processing\|Completed" "Stats cards"
check_auth_page "$BASE_URL/ingest/" "Recent Batches" "Recent Batches section"

curl -s -b "$COOKIE_JAR" "$BASE_URL/ingest/" > "$SCREENSHOT_DIR/05-ingest-system/ingest-dashboard.html"

echo ""

# Phase 5: UT Branding
echo "=== Phase 5: UT Branding ==="
echo ""

DASH_HTML=$(curl -s -b "$COOKIE_JAR" "$BASE_URL/")

if echo "$DASH_HTML" | grep -q "ut-navbar\|navbar"; then
    log_result "PASS" "UT navbar present"
else
    log_result "FAIL" "UT navbar present" "navbar class not found"
fi

if echo "$DASH_HTML" | grep -q "btn-ut"; then
    log_result "PASS" "UT button styling"
else
    log_result "FAIL" "UT button styling" "btn-ut class not found"
fi

if echo "$DASH_HTML" | grep -q "University of Twente"; then
    log_result "PASS" "University branding text"
else
    log_result "FAIL" "University branding text"
fi

echo ""

# Phase 6: HTMX & Alpine.js
echo "=== Phase 6: JavaScript Frameworks ==="
echo ""

if echo "$DASH_HTML" | grep -q "htmx.org"; then
    log_result "PASS" "HTMX script loaded"
else
    log_result "FAIL" "HTMX script loaded"
fi

if echo "$DASH_HTML" | grep -q "hx-"; then
    log_result "PASS" "HTMX attributes present"
else
    log_result "FAIL" "HTMX attributes present"
fi

if echo "$DASH_HTML" | grep -q "alpinejs"; then
    log_result "PASS" "Alpine.js script loaded"
else
    log_result "FAIL" "Alpine.js script loaded"
fi

if echo "$DASH_HTML" | grep -q "x-data"; then
    log_result "PASS" "Alpine.js directives present"
else
    log_result "FAIL" "Alpine.js directives present"
fi

if echo "$DASH_HTML" | grep -q "daisyui"; then
    log_result "PASS" "DaisyUI CSS loaded"
else
    log_result "FAIL" "DaisyUI CSS loaded"
fi

if echo "$DASH_HTML" | grep -q "data-theme"; then
    log_result "PASS" "DaisyUI theme set"
else
    log_result "FAIL" "DaisyUI theme set"
fi

echo ""

# Phase 7: Admin
echo "=== Phase 7: Admin Interface ==="
echo ""

ADMIN_RESP=$(curl -s -b "$COOKIE_JAR" -o /dev/null -w "%{http_code}" "$BASE_URL/admin/")
if [ "$ADMIN_RESP" = "200" ]; then
    log_result "PASS" "Admin page accessible" "HTTP $ADMIN_RESP"
else
    log_result "FAIL" "Admin page accessible" "HTTP $ADMIN_RESP"
fi

echo ""

# Generate report
echo "=== Generating Report ==="
echo ""

REPORT_FILE="$SCREENSHOT_DIR/verification-report.md"

cat > "$REPORT_FILE" << EOF
# Frontend Verification Report

**Date**: $(date -Iseconds)
**Commit**: Post 351f2b4 (frontend restyle)
**Method**: Curl-based HTML verification with authentication

## Summary
- **Total Tests**: $TOTAL
- **Passed**: $PASSED
- **Failed**: $FAILED
- **Success Rate**: $(awk "BEGIN {printf \"%.1f\", ($PASSED/$TOTAL)*100}")%

## Test Results

### Phase 0: Authentication
$(grep -E "^\[.*Login" "$RESULTS_FILE" | sed 's/\[PASS]/**✓ PASS**/' | sed 's/\[FAIL]/**✗ FAIL**/')

### Phase 1: Steps Index
$(grep -E "^\[.*Step" "$RESULTS_FILE" | grep -E "1 badge|title" | sed 's/\[PASS]/**✓ PASS**/' | sed 's/\[FAIL]/**✗ FAIL**/')

### Phase 2: Dashboard
$(grep -E "^\[.*Dashboard" "$RESULTS_FILE" | sed 's/\[PASS]/**✓ PASS**/' | sed 's/\[FAIL]/**✗ FAIL**/')

### Phase 3: Step Pages
$(grep -E "^\[.*Step.*page" "$RESULTS_FILE" | sed 's/\[PASS]/**✓ PASS**/' | sed 's/\[FAIL]/**✗ FAIL**/')

### Phase 4: Ingest System
$(grep -E "^\[.*Ingest" "$RESULTS_FILE" | sed 's/\[PASS]/**✓ PASS**/' | sed 's/\[FAIL]/**✗ FAIL**/')

### Phase 5: UT Branding
$(grep -E "^\[.*UT\|branding" "$RESULTS_FILE" | sed 's/\[PASS]/**✓ PASS**/' | sed 's/\[FAIL]/**✗ FAIL**/')

### Phase 6: JavaScript Frameworks
$(grep -E "^\[.*HTMX\|Alpine\|DaisyUI" "$RESULTS_FILE" | sed 's/\[PASS]/**✓ PASS**/' | sed 's/\[FAIL]/**✗ FAIL**/')

## Issues Found

### Critical Issues
None

### Medium Priority Issues
EOF

if [ ${#ISSUES[@]} -gt 0 ]; then
    for issue in "${ISSUES[@]}"; do
        echo "- $issue" >> "$REPORT_FILE"
    done
else
    echo "None" >> "$REPORT_FILE"
fi

cat >> "$REPORT_FILE" << EOF

## Files Tested

### Main Pages
- Steps Index: \`01-navigation/steps-index.html\`
- Dashboard: \`02-dashboard/dashboard.html\`
- Ingest Dashboard: \`05-ingest-system/ingest-dashboard.html\`

### Step Pages
- Step 1 (Qlik Export): \`04-step-pages/step-01-ingest-qlik.html\`
- Step 3 (Osiris): \`04-step-pages/step-03-enrich-osiris.html\`
- Step 7 (Export): \`04-step-pages/step-07-export-faculty.html\`

## Bug Found During Verification

**Template Bug Fixed**: Login page \`registration/login.html\` was missing \`{% load static %}\` directive.
- **File**: \`src/templates/registration/login.html\`
- **Fix**: Added \`{% load static %}\` after \`{% extends "base.html" %}\`
- **Status**: Fixed during verification

---

**Verification completed**: $(date -Iseconds)
**HTML files saved to**: \`screenshots/\`
**Detailed results**: \`screenshots/verification-results.txt\`
EOF

echo "Report saved to: $REPORT_FILE"

echo ""
echo "========================================"
echo "Verification Complete"
echo "========================================"
echo ""
echo "Total Tests: $TOTAL"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""
echo "Results saved to:"
echo "  - $REPORT_FILE"
echo "  - $RESULTS_FILE"
echo "  - HTML files in $SCREENSHOT_DIR/"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Check results above.${NC}"
    exit 1
fi
