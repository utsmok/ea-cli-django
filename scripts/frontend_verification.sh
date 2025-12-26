#!/bin/bash
set -e

BASE_URL="${1:-http://localhost:8000}"

echo "Verifying Easy Access Platform at $BASE_URL..."

# Check Health
echo -n "Checking API Health... "
curl -s -f "$BASE_URL/api/v1/health/" > /dev/null
echo "OK"

# Check Readiness
echo -n "Checking API Readiness... "
curl -s -f "$BASE_URL/api/v1/readiness/" > /dev/null
echo "OK"

# Check Frontend Login Page
echo -n "Checking Login Page... "
curl -s -f "$BASE_URL/accounts/login/" > /dev/null
echo "OK"

echo "All checks passed!"
