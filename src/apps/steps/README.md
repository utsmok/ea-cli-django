# Steps App Documentation

The Steps app provides a user-friendly interface for running each processing step independently. Each step has its own dedicated UI that follows a consistent pattern.

## Overview

The Easy Access platform processes copyright data through seven distinct steps:

1. **Ingest Qlik Export** - Import Qlik export files to create new items
2. **Ingest Faculty Sheet** - Update classification fields from faculty sheets
3. **Enrich from Osiris** - Fetch course and teacher data from Osiris
4. **Enrich from People Pages** - Scrape person information from UT pages
5. **Get PDF Status from Canvas** - Check Canvas for PDF metadata
6. **Extract PDF Details** - Parse PDFs to extract text and metadata
7. **Export Faculty Sheets** - Generate Excel workbooks for faculty review

## Step Interface Structure

Each step interface follows a consistent three-column layout:

### Left Column (2/3 width)

- **Input Selection**: Choose items from database or upload files
- **Settings**: Configure step-specific settings (API keys, thresholds, etc.)
- **Action Button**: Run the step with selected inputs and settings

### Right Column (1/3 width)

- **Progress**: Real-time progress updates during execution
- **Quick Stats**: Summary statistics relevant to the step

### Bottom Section (Full width)

- **Results**: Detailed results with change logs and error messages

## Step 1: Ingest Qlik Export

**Purpose**: Import Qlik export files to create new CopyrightItem records or update system fields.

**Input**: Excel file (.xlsx, .xls) from Qlik export

**Key Features**:
- Drag-and-drop file upload
- Auto-processing option
- Creates new items or updates system fields
- Never modifies human-annotated fields

**Required Columns**:
- Material ID (unique identifier)
- Title, Author, Publisher
- Course Code, Department, Period
- URL (Canvas file link)

**Settings**:
- Auto-process: Automatically stage and process after upload

**Results**:
- Items created count
- Items updated count
- Recent batch history

## Step 2: Ingest Faculty Sheet

**Purpose**: Update classification and workflow fields from faculty-edited Excel sheets.

**Input**: Excel file (.xlsx, .xls) exported from this system and edited by faculty

**Key Features**:
- Faculty selection dropdown
- Drag-and-drop file upload
- Only updates human-annotated fields
- Cannot create new items

**Editable Fields**:
- Workflow Status (ToDo, InProgress, Done)
- Classifications (old and new system)
- Remarks and notes
- Manual identifiers

**Settings**:
- Faculty Code: Required for tracking
- Auto-process: Apply updates immediately

**Results**:
- Items updated count
- Faculty-specific batch history

## Step 3: Enrich from Osiris

**Purpose**: Fetch course details, teachers, and program information from Osiris.

**Input**: Select items from database (with course codes)

**Key Features**:
- Enrich all items or select specific items
- Item table with selection checkboxes
- Real-time progress tracking
- Polls status every 3 seconds

**Settings**:
- Osiris Base URL (configured in environment)
- Timeout settings
- Teacher detail fetching

**Progress Display**:
- Progress percentage
- Processed count
- Failed count
- Remaining count

**Results**:
- New courses linked
- Teachers found
- PDFs attached
- Detailed change logs

## Step 4: Enrich from People Pages

**Purpose**: Scrape person information from UT people pages.

**Status**: Currently integrated with Step 3 (Osiris enrichment)

**Note**: This step will be separated in a future update to allow independent execution.

## Step 5: Get PDF Status from Canvas

**Purpose**: Check Canvas API for PDF metadata and download status.

**Input**: Select items with Canvas URLs

**Key Features**:
- Check all items or select specific items
- Item table showing URL and PDF status
- Canvas API integration

**Settings**:
- Canvas API URL (configured in environment)
- Canvas API Token (stored securely)
- Auto-download option

**Results**:
- PDFs found and downloaded
- Metadata retrieved
- Error messages for failed downloads

## Step 6: Extract PDF Details

**Purpose**: Parse downloaded PDFs to extract text, metadata, and quality scores.

**Input**: Select items with downloaded PDFs

**Key Features**:
- Extract all unparsed PDFs or select specific items
- OCR using PaddleOCR with GPU support
- Entity extraction with spaCy
- Language detection

**Settings**:
- OCR Engine: PaddleOCR (GPU)
- Quality Threshold: Minimum score for extraction
- Entity extraction: Enable/disable
- Language detection: Enable/disable

**Results**:
- Text extracted
- Quality scores
- Detected entities
- Language information

## Step 7: Export Faculty Sheets

**Purpose**: Generate Excel workbooks for faculty review and classification.

**Input**: Select all faculties or specific faculty

**Key Features**:
- Faculty selection
- Workflow-based organization
- Two-sheet structure (Complete data + Data entry)
- Conditional formatting
- Automatic backups

**Export Structure**:
Each faculty export includes:
- `inbox.xlsx` - Items with status "ToDo"
- `in_progress.xlsx` - Items with status "InProgress"
- `done.xlsx` - Items with status "Done"
- `overview.xlsx` - All items for the faculty

**Settings**:
- Export scope: All or specific faculty
- Protected columns
- Conditional formatting rules

**Results**:
- Files generated
- Export location
- Recent export history

## Navigation

Access the steps interface through:
1. Main navigation bar: Click "Steps"
2. Direct URL: `/steps/`

Each step card on the index page shows:
- Step number and title
- Brief description
- Tags indicating the type of operation
- Direct link to the step interface

## HTMX Integration

All steps use HTMX for dynamic interactions:

- **Progress Updates**: Auto-refresh via polling
- **Form Submissions**: No page reload required
- **Status Badges**: Real-time updates
- **Result Loading**: Partial page updates

## API Endpoints

Each step exposes API endpoints:

- `POST /steps/{step}/run/` - Trigger step execution
- `GET /steps/{step}/status/` - Get execution status
- `GET /steps/{step}/results/` - Fetch results

## Error Handling

All steps include comprehensive error handling:

- **Validation Errors**: Displayed inline in forms
- **Processing Errors**: Shown in results section
- **Network Errors**: Graceful degradation with retry options
- **Timeout Errors**: Clear messages with manual retry

## Permissions

All step interfaces require authentication:
- Users must be logged in to access any step
- Some steps may require staff privileges (configurable)

## Testing

Run tests for the steps app:

```bash
pytest src/apps/steps/tests/
```

Test coverage includes:
- View access and permissions
- Form validation
- HTMX responses
- Progress tracking
- Result display

## Future Enhancements

Planned improvements:
- Separate People Page enrichment (Step 4) from Osiris
- Async task integration for Steps 5-6
- Batch scheduling and queuing
- Export history tracking
- Step chaining (run multiple steps in sequence)
- Progress notifications (email, Slack)
