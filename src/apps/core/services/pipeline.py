"""Legacy pipeline service (deprecated).

This module originally contained a StagedItem-based pipeline. Phase A replaced
this with the `apps.ingest` batch pipeline (IngestionBatch + staging tables +
BatchProcessor), and `apps.core.ChangeLog` for auditing.
"""


class PipelineService:  # pragma: no cover
    def __init__(self):
        raise RuntimeError(
            "PipelineService is deprecated. Use the Phase A ingestion pipeline: "
            "apps.ingest.tasks.stage_batch/process_batch."
        )
