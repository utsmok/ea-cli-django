"""
Update Service: Handles inline edits and workflow transitions.

Responsibilities:
- Field validation before save
- Auto-transition logic (ToDo → InProgress when classified)
- ChangeLog creation for audit trail
- User tracking

This ensures all updates follow consistent business rules.
"""

from __future__ import annotations

from typing import Literal

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.core.models import (
    ChangeLog,
    CopyrightItem,
    WorkflowStatus,
    ClassificationV2,
    OvernameStatus,
    Lengte,
)

User = get_user_model()


class ItemUpdateService:
    """
    Service for updating CopyrightItem fields with audit logging.

    All inline edits go through this service to ensure:
    1. Consistent validation
    2. Proper change logging
    3. Workflow automation
    4. User attribution
    """

    # Fields that can be edited inline
    EDITABLE_FIELDS = {
        "workflow_status",
        "v2_manual_classification",
        "v2_overnamestatus",
        "v2_lengte",
        "remarks",
    }

    def __init__(self, user: User | None = None):
        """
        Initialize service with optional user for audit logging.

        If no user provided, falls back to system user.
        """
        self.user = user or self._get_system_user()

    def update_field(
        self,
        item: CopyrightItem,
        field_name: str,
        value: str,
    ) -> UpdateResult:
        """
        Update a single field on an item.

        Returns UpdateResult containing:
        - updated_item: The saved item
        - changes_made: Dict of {field: (old_value, new_value)}
        - workflow_transitioned: Whether status auto-changed
        - error: Error message if validation failed

        This method is fully testable - just call with a mock item.
        """
        # Validate field is editable
        if field_name not in self.EDITABLE_FIELDS:
            return UpdateResult(
                updated_item=None,
                changes_made={},
                workflow_transitioned=False,
                error=f"Field '{field_name}' is not editable",
            )

        # Get old value for change logging
        old_value = getattr(item, field_name, None)

        # Validate value against choices if applicable
        validation_error = self._validate_field(field_name, value)
        if validation_error:
            return UpdateResult(
                updated_item=None,
                changes_made={},
                workflow_transitioned=False,
                error=validation_error,
            )

        # Track changes and apply update
        changes = {field_name: {"old": old_value, "new": value}}

        with transaction.atomic():
            # Set new value
            setattr(item, field_name, value)

            # Auto-transition: ToDo → InProgress when classification set
            workflow_transitioned = False
            if (
                field_name == "v2_manual_classification"
                and value != ClassificationV2.ONBEKEND
                and item.workflow_status == WorkflowStatus.TODO
            ):
                old_status = item.workflow_status
                item.workflow_status = WorkflowStatus.IN_PROGRESS
                changes["workflow_status"] = {
                    "old": old_status,
                    "new": WorkflowStatus.IN_PROGRESS,
                }
                workflow_transitioned = True

            # Save and log changes
            item.save()
            self._log_changes(item, changes)

        return UpdateResult(
            updated_item=item,
            changes_made=changes,
            workflow_transitioned=workflow_transitioned,
            error=None,
        )

    def _validate_field(self, field_name: str, value: str) -> str | None:
        """
        Validate a field value.

        Returns error message if invalid, None if valid.
        """
        if field_name == "workflow_status":
            valid_choices = [choice[0] for choice in WorkflowStatus.choices]
            if value not in valid_choices:
                return f"Invalid workflow status: {value}"

        elif field_name == "v2_manual_classification":
            valid_choices = [choice[0] for choice in ClassificationV2.choices]
            if value not in valid_choices:
                return f"Invalid classification: {value}"

        elif field_name == "v2_overnamestatus":
            valid_choices = [choice[0] for choice in OvernameStatus.choices]
            if value not in valid_choices:
                return f"Invalid overname status: {value}"

        elif field_name == "v2_lengte":
            valid_choices = [choice[0] for choice in Lengte.choices]
            if value not in valid_choices:
                return f"Invalid lengte: {value}"

        # Remarks is a text field - always valid
        elif field_name == "remarks":
            pass

        return None

    def _log_changes(self, item: CopyrightItem, changes: dict):
        """Create ChangeLog entry for audit trail."""
        ChangeLog.objects.create(
            item=item,
            changes=changes,
            changed_by=self.user,
            change_source=ChangeLog.ChangeSource.MANUAL_EDIT,
        )

    def _get_system_user(self) -> User:
        """Get or create system user for unauthenticated updates."""
        from django.contrib.auth.hashers import make_password

        user, created = User.objects.get_or_create(
            username="system",
            defaults={
                "password": make_password(None),  # Unusable password
                "is_staff": False,
                "is_superuser": False,
            }
        )
        return user


class UpdateResult:
    """Value object for single update results."""

    def __init__(
        self,
        updated_item: CopyrightItem | None,
        changes_made: dict,
        workflow_transitioned: bool,
        error: str | None,
    ):
        self.updated_item = updated_item
        self.changes_made = changes_made
        self.workflow_transitioned = workflow_transitioned
        self.error = error
