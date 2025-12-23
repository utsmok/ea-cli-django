# Project Workflow

## Guiding Principles

1. **The Plan is the Source of Truth:** All work must be tracked in `plan.md`
2. **The Tech Stack is Deliberate:** Changes to the tech stack must be documented in `tech-stack.md` *before* implementation
3. **Test-Driven Development:** Write unit tests before implementing functionality
4. **High Code Coverage:** Aim for >80% code coverage for all modules
5. **User Experience First:** Every decision should prioritize user experience
6. **Non-Interactive & CI-Aware:** Prefer non-interactive commands. Use `CI=true` for watch-mode tools (tests, linters) to ensure single execution.

## Task Workflow

All tasks follow a strict lifecycle:

### Standard Task Workflow

1. **Select Task:** Choose the next available task from `plan.md` in sequential order

2. **Mark In Progress:** Before beginning work, edit `plan.md` and change the task from `[ ]` to `[~]`

3. **Write Failing Tests (Red Phase):**
   - Create a new test file for the feature or bug fix.
   - Write one or more unit tests that clearly define the expected behavior and acceptance criteria for the task.
   - **CRITICAL:** Run the tests and confirm that they fail as expected. This is the "Red" phase of TDD. Do not proceed until you have failing tests.

4. **Implement to Pass Tests (Green Phase):**
   - Write the minimum amount of application code necessary to make the failing tests pass.
   - Run the test suite again and confirm that all tests now pass. This is the "Green" phase.

5. **Refactor (Optional but Recommended):**
   - With the safety of passing tests, refactor the implementation code and the test code to improve clarity, remove duplication, and enhance performance without changing the external behavior.
   - Rerun tests to ensure they still pass after refactoring.

6. **Verify Coverage:** Run coverage reports using the project's chosen tools. For example:
   ```bash
   uv run pytest --cov=src/apps --cov-report=html
   ```
   Target: >80% coverage for new code.

7. **Document Deviations:** If implementation differs from tech stack:
   - **STOP** implementation
   - Update `tech-stack.md` with new design
   - Add dated note explaining the change
   - Resume implementation

8. **Commit Code Changes:**
   - Stage all code changes related to the task.
   - Propose a clear, concise commit message e.g, `feat(ui): Create basic HTML structure for calculator`.
   - Perform the commit.

9. **Update Plan with Commit SHA:**
   - Get the short commit hash: `git log -1 --format="%h"`
   - Update `plan.md`, find the line for the completed task, and append the commit SHA
   - Example: `- [x] Task: Implement feature [abc1234]`
   - Commit the plan update: `conductor(plan): Mark task 'Implement feature' as complete`

### Phase Completion Verification Protocol

**Trigger:** Executed after completing a task that concludes a phase in `plan.md`.

1.  **Announce Protocol Start:** Inform the user that the phase is complete and verification has begun.

2.  **Ensure Test Coverage for Phase Changes:**
    -   **Step 2.1: Determine Phase Scope:** Find the Git commit SHA of the *previous* phase's checkpoint (or first commit if no checkpoint exists).
    -   **Step 2.2: List Changed Files:** Execute `git diff --name-only <previous_checkpoint_sha> HEAD` to get a precise list of all modified files.
    -   **Step 2.3: Verify and Create Tests:** For each code file (exclude `.json`, `.md`, `.yaml`):
        -   Verify a corresponding test file exists.
        -   If a test file is missing, **create one** following existing test patterns in the repository.

3.  **Execute Automated Tests:**
    -   **Step 3.1: Announce command:** "I will now run the automated test suite. **Command:** `uv run pytest`"
    -   **Step 3.2: Execute:** Run the announced command.
    -   **Step 3.3: Handle Failures:** If tests fail, attempt fixes (maximum 2 attempts). If still failing, report and ask for guidance.

4.  **Propose Automated Verification (where possible):**
    -   **CRITICAL:** Before proposing manual verification, analyze `product.md`, `product-guidelines.md`, and `plan.md` to determine if testing can be automated.
    -   **Prefer Automated Tests:**
        ```
        The automated tests have passed. Based on the implementation, the following automated verification is recommended:

        **Automated Verification Steps:**
        1.  Run integration tests: `uv run pytest src/apps/<app>/tests/test_integration.py`
        2.  Run export parity script: `uv run python src/scripts/compare_exports.py <legacy> <new>`
        3.  Verify schema: `uv run python src/manage.py check`
        ```
    -   **Manual Verification Only When Necessary:**
        ```
        The automated tests have passed. For final verification, please follow these steps:

        **Manual Verification Steps:**
        1.  **Start the development server:** `uv run python src/manage.py runserver`
        2.  **Open your browser to:** `http://localhost:8000`
        3.  **Confirm that you see:** [specific expected behavior]
        ```

5.  **Await Explicit User Feedback:**
    -   Ask: "**Does this meet your expectations? Please confirm with yes or provide feedback on what needs to be changed.**"
    -   **PAUSE** and await the user's response.

6.  **Create Checkpoint Commit:**
    -   Stage all changes. Create empty commit if no changes: `git commit --allow-empty`
    -   Commit message: `conductor(checkpoint): Checkpoint end of Phase X`

7.  **Record Phase Checkpoint SHA:**
    -   Get the short commit hash: `git log -1 --format="%h"`
    -   Update `plan.md`, find the phase heading, and append `[checkpoint: <sha>]`
    -   Commit the plan update

8.  **Announce Completion:** Inform the user that the phase is complete with checkpoint recorded.

## Quality Gates

Before marking any task complete, verify:

- [ ] All tests pass
- [ ] Code coverage meets requirements (>80%)
- [ ] Code follows project's code style guidelines (as defined in `code_styleguides/`)
- [ ] All public functions/methods are documented (e.g., docstrings, type hints)
- [ ] Type safety is enforced
- [ ] No linting or static analysis errors
- [ ] Works correctly on mobile (if applicable)
- [ ] Documentation updated if needed
- [ ] No security vulnerabilities introduced

## Development Commands

### Setup
```bash
# Install dependencies
uv sync

# Copy environment template
cp .env.example .env
# Edit .env with your configuration
```

### Daily Development
```bash
# Run development server
uv run python src/manage.py runserver

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/apps --cov-report=html

# Format code
uv run ruff format src/

# Lint code
uv run ruff check src/

# Fix linting issues automatically
uv run ruff check src/ --fix
```

### Before Committing
```bash
# Run all checks (format, lint, test)
uv run ruff format src/ && uv run ruff check src/ --fix && uv run pytest
```

### Django Management Commands
```bash
# Database migrations
uv run python src/manage.py makemigrations
uv run python src/manage.py migrate

# Create superuser
uv run python src/manage.py createsuperuser

# Load legacy data
uv run python src/manage.py load_legacy_data --dry-run
uv run python src/manage.py load_legacy_data --skip-faculties

# Export faculty sheets
uv run python src/manage.py export_faculty_sheets --faculty BMS

# Verify migration
uv run python src/manage.py verify_migration
```

## Testing Requirements

### Unit Testing
- Every module must have corresponding tests.
- Use appropriate test setup/teardown mechanisms.
- Mock external dependencies.
- Test both success and failure cases.

### Integration Testing
- Test complete user flows
- Verify database transactions
- Test authentication and authorization
- Check form submissions

### Manual Testing (When Automation Is Not Possible)
- Document specific steps to manually verify
- Include expected outcomes
- Test on actual devices when possible
- Verify responsive layouts

## Code Review Process

### Self-Review Checklist
Before requesting review:

1. **Functionality**
   - Feature works as specified
   - Edge cases handled
   - Error messages are user-friendly

2. **Code Quality**
   - Follows style guide
   - DRY principle applied
   - Clear variable/function names
   - Appropriate comments

3. **Testing**
   - Unit tests comprehensive
   - Integration tests pass
   - Coverage adequate (>80%)

4. **Security**
   - No hardcoded secrets
   - Input validation present
   - SQL injection prevented
   - XSS protection in place

5. **Performance**
   - Database queries optimized
   - Images optimized
   - Caching implemented where needed

6. **Mobile Experience**
   - Touch targets adequate (44x44px)
   - Text readable without zooming
   - Performance acceptable on mobile
   - Interactions feel native

## Commit Guidelines

### Message Format
```
<type>(<scope>): <description>

[optional body]
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests
- `chore`: Maintenance tasks
- `conductor`: Plan/workflow updates

### Examples
```bash
git commit -m "feat(auth): Add remember me functionality"
git commit -m "fix(posts): Correct excerpt generation for short posts"
git commit -m "test(comments): Add tests for emoji reaction limits"
git commit -m "conductor(plan): Mark task 'Create user model' as complete"
```

## Definition of Done

A task is complete when:

1. All code implemented to specification
2. Unit tests written and passing
3. Code coverage meets project requirements
4. Documentation complete (if applicable)
5. Code passes all configured linting and static analysis checks
6. Works beautifully on mobile (if applicable)
7. Implementation notes added to `plan.md`
8. Changes committed with proper message
9. Plan updated with commit SHA

## Deployment Workflow

### Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Coverage >80%
- [ ] No linting errors
- [ ] Mobile testing complete (if applicable)
- [ ] Environment variables configured
- [ ] Database migrations ready
- [ ] Backup created

### Deployment Steps
1. Merge feature branch to main
2. Tag release with version
3. Build and push to deployment service
4. Run database migrations
5. Verify deployment
6. Test critical paths
7. Monitor for errors

### Post-Deployment
1. Monitor analytics
2. Check error logs
3. Gather user feedback
4. Plan next iteration

## Continuous Improvement

- Review workflow regularly
- Update based on pain points
- Document lessons learned
- Optimize for user happiness
- Keep things simple and maintainable
