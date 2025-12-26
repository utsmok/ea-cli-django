"""
Dashboard services for query building, updates, and detail data assembly.

This service layer separates business logic from views for testability
and maintainability.
"""

from .detail_service import ItemDetailData, ItemDetailService
from .query_service import ItemQueryFilter, ItemQueryService, PaginatedResult
from .update_service import ItemUpdateService, UpdateResult

__all__ = [
    "ItemDetailData",
    "ItemDetailService",
    "ItemQueryFilter",
    "ItemQueryService",
    "ItemUpdateService",
    "PaginatedResult",
    "UpdateResult",
]
