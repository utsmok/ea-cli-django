# Product & Development Guidelines

This document outlines the conventions, styles, and rules for developing the Easy Access Platform. Adherence to these guidelines is mandatory for all contributors, including human developers and AI agents.

## 1. Documentation

### 1.1. Tone & Audience
- **Technical Documentation:** (e.g., specs, plans, logs) Must be professional, concise, and technically precise.
- **User Documentation:** (e.g., guides for Copyright Office/Faculty) Must be instructional, user-centric, and easy to understand, while remaining concise.

### 1.2. Structure
- **Hybrid Specification:** All technical documents (e.g., spec.md, plan.md) must include a mandatory **"User Impact & Instructions"** section written in plain, non-technical language.
- **Verification Checklists:** Every task or feature implementation plan must include a "Success Criteria" or "Verification" checklist to ensure quality and requirement fulfillment.
- **Contextual References:** To maintain clarity and traceability, documents should make frequent use of file-level links (e.g., [MODIFY] apps/core/models.py) and references to the legacy ea-cli codebase where relevant.

## 2. Development & Code Style

### 2.1. Core Tooling
- **Environment & Execution:** All Python scripts, including Django management commands, **must** be run through uv. Never use python directly.
  - **Correct:** uv run python src/manage.py migrate
  - **Incorrect:** python src/manage.py migrate
- **Dependency Management:** All Python packages **must** be managed using uv.
  - **Add:** uv add <package-name>
  - **Remove:** uv remove <package-name>
  - **Sync:** uv sync
- **Linting & Formatting:** ruff is the definitive tool for all linting, formatting, and code checking. All code must pass `uv run ruff check src/` and `uv run ruff format src/` before being committed.
- **Testing:** All tests must be run using uv: `uv run pytest`

### 2.2. Code Conventions
- **Mimic Existing Patterns:** Before making any changes, contributors (especially AI agents) **must** analyze the surrounding code and rigorously mimic existing architectural patterns, naming conventions, and style.
- **Type Hinting:** All new code must use modern Python type hints (| for unions, list instead of List). Do not use the typing module for types that are now built-in.
  - **Correct:** def get_user(user_id: int) -> User | None:
  - **Incorrect:** from typing import Optional; def get_user(user_id: int) -> Optional[User]:
- **Docstrings:** All modules, classes, and functions **must** have comprehensive docstrings formatted in Google or NumPy style to support automated documentation generation.
- **Comments:** Code comments should be used sparingly. They must explain the *why* behind complex or non-obvious logic, never the *what*.

### 2.3. Code Quality Standards
- **Line Length:** 88 characters (ruff default)
- **Python Version:** 3.13
- **Async-First:** Prefer async implementations for I/O-bound operations
- **Test Coverage:** Aim for >80% coverage for new code

## 3. Automated Testing Over Manual Verification

### 3.1. Preference for Automation
Before proposing manual verification steps, always evaluate if the verification can be automated through:
- Unit tests
- Integration tests
- End-to-end tests
- Script-based validation
- Comparison tools

### 3.2. When to Use Manual Verification
Manual verification should only be proposed when:
1. The verification requires subjective visual assessment (UI polish, responsive design)
2. The verification involves physical device testing (mobile touch interactions)
3. The verification requires access to external systems not available in test environment
4. Automated testing would be prohibitively expensive or complex to implement

### 3.3. Examples of Automatable vs Manual Verification

| Type | Automatable | Example |
|------|-------------|---------|
| API endpoints | ✅ Yes | Integration tests verify endpoints return correct data |
| Database queries | ✅ Yes | Tests verify query results match expected values |
| Export parity | ✅ Yes | compare_exports.py script compares outputs |
| File operations | ✅ Yes | Tests verify files created/deleted correctly |
| UI accessibility | ⚠️ Partial | Automated linters exist, but manual testing recommended |
| Visual design | ❌ No | Manual verification of layout, colors, spacing |
| Mobile touch | ❌ No | Requires physical device testing |

## 4. Git Workflow

### 4.1. Commit Messages
Follow conventional commit format:
```
<type>(<scope>): <description>

[optional body]
```

Types: feat, fix, docs, style, refactor, test, chore, conductor

### 4.2. Branch Strategy
- `main`: Production-ready code
- Feature branches: `feature/<description>` or `<ticket>/<description>`
- Bugfix branches: `fix/<description>` or `<ticket>/<description>`

### 4.3. Plan Tracking
- All work must be tracked in `conductor/tracks/*/plan.md`
- Mark tasks as `[~]` when in progress, `[x]` when complete
- Append commit SHA to completed tasks: `- [x] Task description [abc1234]`
- No git notes required (simplified workflow)

## 5. Security & Privacy

### 5.1. Secrets Management
- Never commit secrets, API keys, or credentials to the repository
- Use environment variables for all configuration
- Provide `.env.example` with placeholder values
- Never log sensitive data

### 5.2. Input Validation
- Validate all user input
- Sanitize data before database operations
- Use Django's built-in security features (CSRF, clickjacking protection)
- Keep dependencies updated

## 6. Performance Guidelines

### 6.1. Database Operations
- Use `select_related()` and `prefetch_related()` to avoid N+1 queries
- Use bulk operations for multiple records
- Add database indexes for frequently queried fields
- Use Polars for large data processing operations

### 6.2. External API Calls
- Implement proper rate limiting
- Cache responses when appropriate
- Use async operations for I/O-bound tasks
- Implement retry logic with exponential backoff

## 7. User Experience

### 7.1. Accessibility
- Ensure keyboard navigation works
- Provide alt text for images
- Use semantic HTML
- Test with screen readers when possible

### 7.2. Responsive Design
- Mobile-first approach
- Touch targets at least 44x44px
- Text readable without zooming
- Test on actual devices when possible

### 7.3. Error Handling
- Provide clear, actionable error messages
- Log errors for debugging
- Graceful degradation for missing features
- User-friendly error pages
