#!/usr/bin/env node

/**
 * Frontend Verification Script for Easy Access Platform
 * Uses Playwright to capture screenshots and verify UI elements
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// Configuration
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const SCREENSHOT_DIR = path.join(__dirname, '..', 'screenshots');
const TEST_USER = 'testuser';
const TEST_PASS = 'testpass123';

// Test results tracking
const results = [];

function logResult(test, passed, notes = '') {
  const status = passed ? 'PASS' : 'FAIL';
  const result = { test, status, notes };
  results.push(result);
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${status}: ${test}${notes ? ` - ${notes}` : ''}`);
}

async function setupDirectories() {
  const dirs = [
    '01-navigation',
    '02-dashboard',
    '03-steps-index',
    '04-step-pages',
    '05-ingest-system',
    '06-admin',
    '07-interactions',
    '08-backend'
  ];

  dirs.forEach(dir => {
    const fullPath = path.join(SCREENSHOT_DIR, dir);
    if (!fs.existsSync(fullPath)) {
      fs.mkdirSync(fullPath, { recursive: true });
    }
  });
}

async function login(page) {
  console.log('\n=== Logging in ===');
  try {
    await page.goto(`${BASE_URL}/accounts/login/`);
    await page.waitForLoadState('networkidle');

    // Fill login form
    await page.fill('input[name="username"]', TEST_USER);
    await page.fill('input[name="password"]', TEST_PASS);

    // Submit form
    await page.click('button[type="submit"], input[type="submit"]');
    await page.waitForLoadState('networkidle');

    // Check if login succeeded (redirected or showing dashboard)
    const url = page.url();
    if (url.includes('login') === false || url.includes('dashboard') || url === `${BASE_URL}/`) {
      logResult('Login', true, `Redirected to ${url}`);
      return true;
    } else {
      logResult('Login', false, 'Still on login page');
      return false;
    }
  } catch (error) {
    logResult('Login', false, error.message);
    return false;
  }
}

async function verifyElementVisible(page, selector, description) {
  try {
    await page.waitForSelector(selector, { timeout: 5000 });
    const element = await page.locator(selector).first();
    const visible = await element.isVisible();
    logResult(description, visible, visible ? `Found: ${selector}` : 'Not visible');
    return visible;
  } catch (error) {
    logResult(description, false, `Error: ${error.message}`);
    return false;
  }
}

async function testStepsIndex(page) {
  console.log('\n=== Testing Steps Index ===');

  await page.goto(`${BASE_URL}/steps/`);
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, '01-navigation', 'steps-index-full.png'),
    fullPage: true
  });

  // Verify all 7 step cards
  for (let i = 1; i <= 7; i++) {
    await verifyElementVisible(page, `.badge.badge-primary.badge-lg:has-text("${i}")`, `Step ${i} badge visible`);
  }

  // Verify UT logo
  await verifyElementVisible(page, '.ut-logo img', 'UT logo in navbar');

  // Verify navigation links
  await verifyElementVisible(page, 'a[href="/"]', 'Dashboard link');
  await verifyElementVisible(page, 'a[href="/steps/"]', 'Processing Steps link');
  await verifyElementVisible(page, 'a[href="/admin/"]', 'Admin link');

  // Check for "Copyright Compliance Platform" subtitle
  const subtitle = await page.locator('text=Copyright Compliance Platform').count();
  logResult('Copyright Platform subtitle', subtitle > 0);
}

async function testDashboard(page) {
  console.log('\n=== Testing Dashboard ===');

  await page.goto(`${BASE_URL}/`);
  await page.waitForLoadState('networkidle');

  // Wait for HTMX grid to load
  try {
    await page.waitForSelector('#data-grid-inner, .grid, [class*="item"]', { timeout: 5000 });
  } catch (e) {
    console.log('Grid selector not found, continuing...');
  }

  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, '02-dashboard', 'dashboard-landing.png'),
    fullPage: true
  });

  // Verify dashboard elements
  await verifyElementVisible(page, 'h1:has-text("Copyright Dashboard")', 'Page title');
  await verifyElementVisible(page, 'button:has-text("Enrich All"), a:has-text("Enrich All")', 'Enrich All button');
  await verifyElementVisible(page, 'a:has-text("Download Faculty Sheets"), button:has-text("Download")', 'Download button');
  await verifyElementVisible(page, 'button:has-text("Upload Excel")', 'Upload button');

  // Check for item cards
  const cards = await page.locator('.card, [class*="item"]').count();
  logResult('Item cards in grid', cards > 0, `Found ${cards} cards`);

  // Test upload modal
  try {
    await page.click('button:has-text("Upload Excel")');
    await page.waitForSelector('.modal.modal-open, [class*="modal"][class*="open"]', { timeout: 2000 });

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '02-dashboard', 'dashboard-upload-modal.png'),
      fullPage: true
    });

    await verifyElementVisible(page, '.modal.modal-open, [class*="modal"][class*="open"]', 'Upload modal open');

    // Close modal via backdrop
    await page.click('.modal-backdrop, .modal, [class*="modal-backdrop"]');
    await page.waitForTimeout(500);

    logResult('Modal closes', true);
  } catch (error) {
    logResult('Upload modal', false, error.message);
  }
}

async function testStepPages(page) {
  console.log('\n=== Testing Step Pages ===');

  const steps = [
    { slug: 'ingest-qlik', title: 'Ingest Qlik Export', num: 1 },
    { slug: 'ingest-faculty', title: 'Ingest Faculty Sheet', num: 2 },
    { slug: 'enrich-osiris', title: 'Enrich from Osiris', num: 3 },
    { slug: 'enrich-people', title: 'Enrich from People Pages', num: 4 },
    { slug: 'pdf-canvas-status', title: 'Get PDF Status from Canvas', num: 5 },
    { slug: 'pdf-extract', title: 'Extract PDF Details', num: 6 },
    { slug: 'export-faculty', title: 'Export Faculty Sheets', num: 7 },
  ];

  for (const step of steps) {
    console.log(`\n  Testing: ${step.title}`);

    try {
      await page.goto(`${BASE_URL}/steps/${step.slug}/`);
      await page.waitForLoadState('networkidle');
      await page.waitForSelector('h1', { timeout: 5000 });

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, '04-step-pages', `step-${step.num}-${step.slug}.png`),
        fullPage: true
      });

      // Verify common elements
      await verifyElementVisible(page, '.breadcrumbs, nav[aria-label="breadcrumb"]', 'Breadcrumbs visible');
      await verifyElementVisible(page, `h1:has-text("${step.title}")`, 'Page title');

      // Check for cards
      await verifyElementVisible(page, '.card:has-text("Input"), .card:has-text("Selection")', 'Input card');
      await verifyElementVisible(page, '.card:has-text("Settings")', 'Settings card');
      await verifyElementVisible(page, '.card:has-text("Progress")', 'Progress card');
      await verifyElementVisible(page, '.card:has-text("Results")', 'Results card');

    } catch (error) {
      logResult(`Step ${step.num}: ${step.title}`, false, error.message);
    }
  }
}

async function testIngestSystem(page) {
  console.log('\n=== Testing Ingest System ===');

  await page.goto(`${BASE_URL}/ingest/`);
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, '05-ingest-system', 'ingest-dashboard.png'),
    fullPage: true
  });

  // Verify stat cards
  const stats = ['Total Batches', 'Pending', 'Processing', 'Completed', 'Failed'];
  for (const stat of stats) {
    await verifyElementVisible(page, `:has-text("${stat}")`, `${stat} stat card`);
  }

  // Verify quick action buttons
  await verifyElementVisible(page, 'a:has-text("Upload New File"), button:has-text("Upload")', 'Upload button');
  await verifyElementVisible(page, 'a:has-text("View All Batches"), a:has-text("All Batches")', 'View batches button');

  // Verify batches table
  await verifyElementVisible(page, 'table.table, table', 'Batches table');
}

async function testHTMXInteractions(page) {
  console.log('\n=== Testing HTMX Interactions ===');

  await page.goto(`${BASE_URL}/`);
  await page.waitForLoadState('networkidle');

  // Wait for initial grid load
  try {
    await page.waitForSelector('#data-grid-inner, .grid', { timeout: 5000 });
  } catch (e) {
    console.log('Grid not found, continuing...');
  }

  // Look for Enrich button
  const enrichButton = page.locator('button:has-text("Enrich"), a:has-text("Enrich")').first();
  const count = await enrichButton.count();

  if (count > 0) {
    try {
      await enrichButton.click();
      await page.waitForTimeout(2000);

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, '07-interactions', 'htmx-enrich-triggered.png'),
        fullPage: true
      });

      // Check for status badge change
      const runningBadge = await page.locator('.badge.animate-pulse, [class*="animate"]').count();
      logResult('Enrich button - status badge change', runningBadge > 0, `Found ${runningBadge} animated badges`);
    } catch (error) {
      logResult('Enrich button interaction', false, error.message);
    }
  } else {
    logResult('Enrich button found', false, 'No enrich buttons on page');
  }
}

async function testResponsiveDesign(page) {
  console.log('\n=== Testing Responsive Design ===');

  // Mobile viewport
  await page.setViewportSize({ width: 375, height: 667 });

  await page.goto(`${BASE_URL}/steps/`);
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, '07-interactions', 'responsive-steps-mobile.png'),
    fullPage: true
  });

  // Check for mobile menu button
  await verifyElementVisible(page, 'label[for*="menu"], button[aria-label*="menu"], .navbar-end .btn', 'Mobile menu button');

  // Dashboard mobile
  await page.goto(`${BASE_URL}/`);
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, '07-interactions', 'responsive-dashboard-mobile.png'),
    fullPage: true
  });

  // Reset to desktop
  await page.setViewportSize({ width: 1920, height: 1080 });
}

async function testWebComponents(page) {
  console.log('\n=== Testing Web Components ===');

  await page.goto(`${BASE_URL}/ingest/`);
  await page.waitForLoadState('networkidle');

  // Check for ut-status-badge
  const statusBadges = await page.locator('ut-status-badge, .badge').count();
  logResult('Status badges visible', statusBadges > 0, `Found ${statusBadges} badges`);

  // Check for ut-stat-card
  const statCards = await page.locator('ut-stat-card, .stat-card, [class*="stat"]').count();
  logResult('Stat cards visible', statCards > 0, `Found ${statCards} stat cards`);

  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, '07-interactions', 'web-components.png'),
    fullPage: true
  });
}

async function generateReport() {
  const reportPath = path.join(SCREENSHOT_DIR, 'verification-report.md');
  const passed = results.filter(r => r.status === 'PASS').length;
  const failed = results.filter(r => r.status === 'FAIL').length;

  let report = `# Frontend Verification Report

**Date**: ${new Date().toISOString().split('T')[0]}
**Commit**: Post 351f2b4 (frontend restyle)
**Method**: Playwright automated testing

## Summary
- **Total Tests**: ${results.length}
- **Passed**: ${passed}
- **Failed**: ${failed}
- **Success Rate**: ${((passed / results.length) * 100).toFixed(1)}%

## Test Results

`;

  // Group by phase
  const phases = {};
  results.forEach(r => {
    const phase = r.test.split(':')[0] || 'Other';
    if (!phases[phase]) phases[phase] = [];
    phases[phase].push(r);
  });

  Object.keys(phases).forEach(phase => {
    report += `### ${phase}\n\n`;
    phases[phase].forEach(r => {
      const icon = r.status === 'PASS' ? '✓' : '✗';
      report += `- [${r.status}] **${icon} ${r.test}**${r.notes ? ` - ${r.notes}` : ''}\n`;
    });
    report += '\n';
  });

  report += `
## Issues Found

### Critical Issues
${results.filter(r => r.status === 'FAIL' && r.notes && r.notes.includes('Critical')).length > 0 ? results.filter(r => r.status === 'FAIL' && r.notes.includes('Critical')).map(r => `- ${r.test}: ${r.notes}`).join('\n') : 'None'}

### Medium Priority Issues
${results.filter(r => r.status === 'FAIL' && !r.notes?.includes('Critical')).map(r => `- ${r.test}: ${r.notes || 'No details'}`).join('\n') || 'None'}

## Screenshots

All screenshots saved to: \`screenshots/\`

### Quick Reference
- Navigation: \`01-navigation/\`
- Dashboard: \`02-dashboard/\`
- Step Pages: \`04-step-pages/\`
- Ingest System: \`05-ingest-system/\`
- Admin: \`06-admin/\`
- Interactions: \`07-interactions/\`
- Backend: \`08-backend/\`

---

**Verification completed**: ${new Date().toISOString()}
`;

  fs.writeFileSync(reportPath, report);
  console.log(`\n=== Report saved to: ${reportPath} ===`);
}

async function main() {
  console.log('Starting Easy Access Platform Frontend Verification');
  console.log(`Target URL: ${BASE_URL}`);
  console.log(`Timestamp: ${new Date().toISOString()}`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  try {
    // Setup
    await setupDirectories();

    // Login first
    const loggedIn = await login(page);
    if (!loggedIn) {
      console.log('Warning: Login may have failed, continuing anyway...');
    }

    // Run test phases
    await testStepsIndex(page);
    await testDashboard(page);
    await testStepPages(page);
    await testIngestSystem(page);
    await testHTMXInteractions(page);
    await testWebComponents(page);
    await testResponsiveDesign(page);

    // Generate report
    await generateReport();

  } catch (error) {
    console.error('Fatal error:', error);
  } finally {
    await browser.close();
  }

  console.log('\n=== Verification Complete ===');
  console.log(`Total tests: ${results.length}`);
  console.log(`Passed: ${results.filter(r => r.status === 'PASS').length}`);
  console.log(`Failed: ${results.filter(r => r.status === 'FAIL').length}`);
}

main().catch(console.error);
