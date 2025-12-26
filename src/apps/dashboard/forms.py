"""
Form classes for dashboard inline editing.

These forms provide:
1. Validation for inline edits
2. CSRF protection
3. Widget rendering for different field types
4. Integration with update service

Forms are kept simple - complex business logic lives in services.
"""

from django import forms

from apps.core.models import (
    CopyrightItem,
    WorkflowStatus,
)


class InlineEditForm(forms.ModelForm):
    """
    Base form for inline editing.

    This form is used via HTMX to validate updates
    before they're saved by the update service.
    """

    class Meta:
        model = CopyrightItem
        fields = [
            "workflow_status",
            "v2_manual_classification",
            "v2_overnamestatus",
            "v2_lengte",
            "remarks",
        ]
        widgets = {
            "workflow_status": forms.Select(
                attrs={
                    "class": "select select-bordered select-sm w-full",
                }
            ),
            "v2_manual_classification": forms.Select(
                attrs={
                    "class": "select select-bordered select-sm w-full",
                }
            ),
            "v2_overnamestatus": forms.Select(
                attrs={
                    "class": "select select-bordered select-sm w-full",
                }
            ),
            "v2_lengte": forms.Select(
                attrs={
                    "class": "select select-bordered select-sm w-full",
                }
            ),
            "remarks": forms.TextInput(
                attrs={
                    "class": "input input-bordered input-sm w-full",
                    "placeholder": "Add remarks...",
                }
            ),
        }


class WorkflowFilterForm(forms.Form):
    """
    Form for workflow filter bar.

    This form:
    - Renders filter controls
    - Validates filter parameters
    - Provides consistent interface for building filter queries
    """

    workflow_status = forms.ChoiceField(
        required=False,
        choices=[("", "All")] + list(WorkflowStatus.choices),
    )

    faculty = forms.ChoiceField(
        required=False,
        choices=[("", "All Faculties")],
    )

    search = forms.CharField(
        required=False,
    )

    per_page = forms.ChoiceField(
        required=False,
        choices=[("25", "25"), ("50", "50"), ("100", "100")],
        initial="50",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically populate faculty choices
        from apps.core.models import Faculty

        faculty_choices = [("", "All Faculties")] + [
            (f.abbreviation, f.abbreviation) for f in Faculty.objects.all()
        ]
        self.fields["faculty"].choices = faculty_choices
