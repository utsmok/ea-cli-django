# Initial Concept
Goal: Refactor a legacy CLI tool (ea-cli) into a web-based Django platform for managing copyright compliance in course materials. Managed by Copyright Office, used by Faculty Staff. Priorities: Parity with legacy, then dashboard.

# Product Guide: Easy Access Platform

## Vision
The Easy Access Platform is a centralized, web-based intelligence hub designed to modernize the management of copyright compliance for university course materials. By refactoring the legacy ea-cli tool into a robust Django-based system, the platform transitions from a fragmented Excel-based workflow to a collaborative environment that scales with high performance and data integrity.

## Core Purpose
To provide a structured, automated, and user-friendly system for the Copyright Office and Faculty Staff to ingest, classify, and enrich copyright data, ensuring compliance while maximizing efficiency through advanced automation and UI enhancements.

## Target Users
*   **Copyright Office Employees:** Administrators who manage the platform, oversee university-wide compliance, onboard users, and generate progress reports.
*   **Faculty Staff:** Designated personnel responsible for adding metadata and classifying course materials for their respective faculties.

## Key Goals
1.  **System Parity & Reliability:** Establish a robust Django-backed ingestion pipeline that replicates the legacy system's inputs and outputs with superior data cleaning and structuring.
2.  **Collaborative Workflow:** Replace local CLI scripts and Excel files with a centralized dashboard enabling real-time collaboration.
3.  **Enhanced User Experience:** Implement a web-based frontend that features a side-by-side view of PDF documents and metadata for streamlined classification.
4.  **Intelligence & Automation:** Integrate automated entity recognition (teachers, authors, publishers) and ML-based classification suggestions to assist human reviewers.
5.  **Smart Deduplication:** Utilize exact content hashing (xxh3_64) and fuzzy matching (heuristics and vector embeddings) to identify similar documents and propagate classification decisions across duplicates.

## Critical Features
*   **Structured Ingestion Pipeline:** A two-phase (Stage ? Process) pipeline for Qlik and Faculty data to ensure integrity and auditability via a ChangeLog.
*   **High-Fidelity Export Suite:** Backward-compatible Excel generation that matches legacy formatting and styling exactly.
*   **Dynamic Dashboard:** A web-based grid for batch management, real-time status updates, and interactive data entry.
*   **Extensible Enrichment Hub:** A modular system to rebuild and verify enrichment data from external sources (Osiris, Canvas) from scratch.
