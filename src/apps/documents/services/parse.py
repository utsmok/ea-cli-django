"""
PDF Parsing service using Kreuzberg.
Ports and modernizes logic from ea-cli/easy_access/pdf/parse.py

Includes:
- Text extraction with PaddleOCR
- Quality scoring
- Language detection
- Keyword extraction
- Content chunking
- Entity extraction (spaCy-based)
"""

import logging
from pathlib import Path

from xxhash import xxh3_64_hexdigest

from apps.documents.models import Document, PDFText

logger = logging.getLogger(__name__)


def hash_pdf(file_path: Path) -> str | None:
    """
    Calculate xxHash of the PDF file.
    """
    try:
        return xxh3_64_hexdigest(file_path.read_bytes())
    except Exception as e:
        logger.error(f"Error hashing PDF {file_path}: {e}")
        return None


async def extract_text_from_pdf(file_path: Path) -> dict | None:
    """
    Extract text and metadata from PDF using Kreuzberg.

    Uses PaddleOCR backend with GPU support.
    Includes:
    - Quality scoring
    - Language detection
    - Keyword extraction
    - Content chunking
    - Entity extraction

    Returns dict with:
        - content: extracted text
        - metadata: PDF metadata (title, author, etc.)
        - quality_score: extraction quality score
        - keywords: extracted keywords
        - detected_language: detected language
        - chunks: list of content chunks
        - entities: extracted entities
        - num_pages: number of pages
    """
    try:
        from kreuzberg import (
            ExtractionConfig,
            PaddleOCRConfig,
            extract_file,
        )

        # Full pipeline config with all features
        config = ExtractionConfig(
            # OCR settings
            ocr_backend="paddleocr",
            ocr_config=PaddleOCRConfig(use_gpu=True, device="cuda"),
            # Quality processing
            enable_quality_processing=True,
            # Language detection
            auto_detect_language=False,
            # Keyword extraction
            extract_keywords=False,
            keyword_count=15,
            # Entity extraction
            extract_entities=False,
        )

        # Extract text
        result = await extract_file(file_path, config=config)
        if not result:
            logger.warning(f"No extraction result for {file_path}")
            return None

        # Extract metadata
        metadata = result.metadata or {}

        # Parse number of pages from summary if available
        num_pages = None
        summary = metadata.get("summary", "")
        if summary and "PDF document with" in summary:
            try:
                num_pages_str = (
                    summary.split("PDF document with")[1].split("pages")[0].strip()
                )
                num_pages = int(num_pages_str)
            except (ValueError, IndexError):
                pass

        # Process chunks
        chunks_data = []
        if hasattr(result, "chunks") and result.chunks:
            for i, chunk in enumerate(result.chunks):
                chunks_data.append({"id": i, "content": chunk[:1000]})

        # Get detected language
        detected_language = None
        if hasattr(result, "detected_languages") and result.detected_languages:
            detected_language = (
                result.detected_languages[0] if result.detected_languages else None
            )
        elif metadata.get("language"):
            detected_language = metadata.get("language")

        # Get keywords
        keywords = []
        if hasattr(result, "keywords") and result.keywords:
            keywords = [x[0] for x in result.keywords]
        elif metadata.get("keywords"):
            keywords = metadata.get("keywords")

        # Get entities
        entities = []
        if hasattr(result, "entities") and result.entities:
            for entity in result.entities:
                if hasattr(entity, "text") and hasattr(entity, "type"):
                    entities.append(
                        {
                            "text": entity.text,
                            "label": entity.type,
                            "start": getattr(entity, "start", None),
                            "end": getattr(entity, "end", None),
                        }
                    )

        results = {
            "content": result.content or "",
            "metadata": metadata,
            "quality_score": metadata.get("quality_score", 0.0),
            "keywords": keywords,
            "detected_language": detected_language,
            "chunks": chunks_data,
            "entities": entities,
            "num_pages": num_pages,
            "title": metadata.get("title"),
            "author": ", ".join(metadata.get("authors", []))
            if metadata.get("authors")
            else None,
            "creator": metadata.get("created_by"),
            "creation_date": metadata.get("created_at"),
            "mod_date": metadata.get("modified_at"),
            "subject": metadata.get("subject"),
            "description": metadata.get("description"),
            "summary": summary,
        }
        return results

    except ImportError as e:
        logger.error(f"Kreuzberg import error: {e}. Is kreuzberg[paddleocr] installed?")
        return None
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {e}")
        import traceback

        traceback.print_exc()
        return None


async def parse_pdfs(
    filter_ids: list[int] | None = None, skip_text: bool = False
) -> dict:
    """
    Parse all PDFs that haven't been processed yet.

    Args:
        filter_ids: Optional list of copyright_item IDs to filter
        skip_text: If True, only hash PDFs without text extraction

    Returns:
        Dictionary with statistics
    """
    from asgiref.sync import sync_to_async

    # Get PDFs that need processing
    @sync_to_async
    def get_documents_to_process():
        queryset = Document.objects.filter(extraction_attempted=False)
        if filter_ids:
            queryset = queryset.filter(items__material_id__in=filter_ids)
        return list(queryset)

    documents = await get_documents_to_process()

    if not documents:
        logger.info("No documents found that need processing")
        return {"processed": 0, "successful": 0, "failed": 0}

    logger.info(f"Processing {len(documents)} documents")

    processed = 0
    successful = 0
    failed = 0

    for doc in documents:
        try:
            # Construct file path
            if not doc.file:
                logger.warning(f"Document {doc.id} has no file")
                failed += 1
                continue

            file_path = Path(doc.file.path)

            if not file_path.exists():
                logger.warning(f"PDF file not found: {file_path}")
                failed += 1
                continue

            # Hash the file
            # Hash should already be there from download, but recalculate if missing
            if not doc.filehash:
                file_hash = hash_pdf(file_path)
                if file_hash:
                    doc.filehash = file_hash

            # Extract text if not skipping
            if not skip_text:
                doc.extraction_attempted = True
                extraction_result = await extract_text_from_pdf(file_path)

                if extraction_result and len(extraction_result.get("content", "")) > 0:
                    doc.extraction_successful = True

                    # Combine chunks and entities for storage
                    # Chunks now also include any extracted entities for that PDF
                    chunks_with_data = extraction_result.get("chunks", [])
                    entities = extraction_result.get("entities", [])
                    # todo: store entities as models + m2m relation

                    # Create PDFText record with all extracted data
                    @sync_to_async
                    def create_pdf_text(
                        result=extraction_result,
                        chunks=chunks_with_data,
                        ents=entities,
                    ):
                        return PDFText.objects.create(
                            extracted_text=result["content"],
                            num_pages=result.get("num_pages"),
                            text_quality=result.get("quality_score", 0.0),
                            detected_language=result.get("detected_language"),
                            extracted_keywords=result.get("keywords"),
                            chunks_with_embeddings={
                                "chunks": chunks,
                                "entities": ents,
                            },
                        )

                    pdf_text = await create_pdf_text()
                    doc.extracted_text = pdf_text

                    # Update document metadata
                    if extraction_result.get("title"):
                        doc.title = extraction_result["title"]
                    if extraction_result.get("author"):
                        doc.author = extraction_result["author"]
                    if extraction_result.get("creator"):
                        doc.creator = extraction_result["creator"]
                    if extraction_result.get("subject"):
                        doc.subject = extraction_result["subject"]
                    if extraction_result.get("summary"):
                        doc.summary = extraction_result["summary"]
                    if extraction_result.get("description"):
                        doc.description = extraction_result["description"]
                    if extraction_result.get("num_pages"):
                        doc.num_pages = extraction_result["num_pages"]
                    if extraction_result.get("keywords"):
                        doc.keywords = extraction_result["keywords"]

                    successful += 1
                else:
                    doc.extraction_successful = False
                    failed += 1
            else:
                successful += 1

            # Save Document record
            @sync_to_async
            def save_doc(document=doc):
                document.save()

            await save_doc()
            processed += 1

        except Exception as e:
            logger.error(f"Error processing Document {doc.id}: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    logger.info(
        f"Parsing complete: {processed} processed, {successful} successful, {failed} failed"
    )
    return {"processed": processed, "successful": successful, "failed": failed}
