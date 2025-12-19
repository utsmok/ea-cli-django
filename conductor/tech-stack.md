# Tech Stack: Easy Access Platform

This document details the core technologies and libraries utilized in the development of the Easy Access Platform.

## 1. Programming Language

- **Python:** Version 3.13

## 2. Core Frameworks

- **Django:** Version 6.0 (Backend web framework)
- **HTMX:** For dynamic frontend interactions
- **Django-Shinobi:** For API schema definition

## 3. Data Management

- **PostgreSQL:** Primary relational database
- **Polars:** High-performance DataFrame library for data processing
- **Redis:** For caching and task queue management (via django-redis)

## 4. Key Libraries & Tools

- **uv:** Python package installer and dependency manager
- **ruff:** Linter, formatter, and type checker for Python code
- **watchfiles:** For monitoring filesystem changes
- **loguru:** For flexible and powerful logging
- **httpx:** Asynchronous HTTP client
- **pypdf:** For PDF manipulation
- **fastexcel / openpyxl:** For reading and writing Excel files
- **kreuzberg:** For PDF text extraction
- **xxhash:** For fast hashing (e.g., document deduplication)
- **beautifulsoup4:** For web scraping (e.g., Osiris enrichment)
- **levenshtein:** For fuzzy string matching
- **tqdm:** For progress bars
- **uvicorn:** ASGI server for production deployment
