"""
Helper functions for views.
"""


def _parse_item_ids(item_ids_str: list[str]) -> tuple[list[int] | None, str | None]:
    """
    Parse and validate item IDs from request.

    Returns:
        Tuple of (parsed_ids, error_message). If successful, error_message is None.

    Validation:
    - Input must not be empty
    - All IDs must be valid positive integers
    - Duplicates are removed while preserving order
    - Position-specific error messages for debugging
    """
    if not item_ids_str:
        return None, "No item IDs provided"

    if not isinstance(item_ids_str, list):
        return (
            None,
            f"Invalid input type: expected list, got {type(item_ids_str).__name__}",
        )

    parsed_ids = []
    seen = set()

    for idx, item_id in enumerate(item_ids_str, 1):
        # Check if string
        if not isinstance(item_id, str):
            return (
                None,
                f"Item ID at position {idx} is not a string: {type(item_id).__name__}",
            )

        # Check if empty
        if not item_id.strip():
            return None, f"Item ID at position {idx} is empty"

        # Try to parse as integer
        try:
            parsed = int(item_id)
        except (ValueError, TypeError):
            return (
                None,
                f"Invalid item ID at position {idx}: '{item_id}' is not a valid integer",
            )

        # Validate range (must be positive)
        if parsed <= 0:
            return (
                None,
                f"Invalid item ID at position {idx}: {parsed} (must be positive)",
            )

        # Remove duplicates while preserving order
        if parsed not in seen:
            seen.add(parsed)
            parsed_ids.append(parsed)

    # Validate we got at least one ID
    if not parsed_ids:
        return None, "No valid item IDs found after parsing"

    return parsed_ids, None
