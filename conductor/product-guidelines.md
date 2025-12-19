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
- **Linting & Formatting:** uff is the definitive tool for all linting, formatting, and code checking. All code must pass uff check . and uff format . before being committed.

### 2.2. Code Conventions
- **Mimic Existing Patterns:** Before making any changes, contributors (especially AI agents) **must** analyze the surrounding code and rigorously mimic existing architectural patterns, naming conventions, and style.
- **Type Hinting:** All new code must use modern Python type hints (| for unions, list instead of List). Do not use the 	yping module for types that are now built-in.
  - **Correct:** def get_user(user_id: int) -> User | None:
  - **Incorrect:** rom typing import Optional; def get_user(user_id: int) -> Optional[User]:
- **Docstrings:** All modules, classes, and functions **must** have comprehensive docstrings formatted in Google or NumPy style to support automated documentation generation.
- **Comments:** Code comments should be used sparingly. They must explain the *why* behind complex or non-obvious logic, never the *what*.
