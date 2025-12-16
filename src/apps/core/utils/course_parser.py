from typing import Any
import logging

logger = logging.getLogger(__name__)

def determine_course_code(code: str | None, name: str | None) -> set[str]:
    """Determines Osiris course code(s) from Canvas course data.

    This function attempts to parse the correct Osiris course code(s) from
    the provided Canvas course code and name.

    The heuristic is as follows:

    STEP 1: Attempt to parse Canvas course code into Osiris course code(s).
        - From the 'course_code' string (e.g., "YYYY - XXXXXXXXXXX - 1A").
        - Extract the middle part as the potential course code.
        - A valid Osiris course code is typically numeric and around 9 digits long.

        Examples:
            - "2024-191158500-JAAR" -> "191158500"
            - "2024-201800005-1A" -> "201800005"

    STEP 2: If Step 1 fails, attempt to parse Canvas course name.
        - This is used when the 'course_code' field contains non-numeric values
          (e.g., "2024-IDVWI-1A"), suggesting multiple codes might be in the name.
        - The 'course_name' might look like:
          "Circuit Analysis 1 and 2; 202001116,202200163 (2024-JAAR)"
        - Extract codes from the part after ';' and before '('.
        - Split by ',' and validate each part.

        Examples:
            - "Circuit Analysis 1 and 2; 202001116,202200163 (2024-JAAR)"
              -> {"202001116", "202200163"}
            - "Characterization of Nanostructures 2023; 193700010,201600043 (2024-1A)"
              -> {"193700010", "201600043"}

    Args:
        code: The course code string from Canvas data.
        name: The course name string from Canvas data.

    Returns:
        A set of valid Osiris course codes found. Returns an empty set if
        no valid codes could be determined.
    """

    code = str(code) if code else ""
    name = str(name) if name else ""

    def is_valid_course_code(check_code: Any) -> bool:
        """Checks if a given string is a plausible Osiris course code."""
        try:
            check_code_str = str(check_code).strip()
            # 202400001 is 9 digits. Some might be 8?
            # Legacy said len >= 8.
            return bool(check_code_str.isdigit() and len(check_code_str) >= 8)
        except Exception:
            return False

    temp_results: set[str] = set()
    first_try_code: str = ""
    second_try_codes_str: str = ""

    try:
        # Step 1: Attempt to parse from 'code'
        parts = code.split("-")
        if len(parts) > 1:
            first_try_code = parts[1].strip()
            if is_valid_course_code(first_try_code):
                temp_results.add(first_try_code)

        # Step 2: Attempt to parse from 'name' if necessary or if name contains codes
        if ";" in name and "(" in name:
            try:
                name_parts = name.split(";", 1)
                if len(name_parts) > 1:
                    codes_section = name_parts[1].split("(", 1)[0]
                    second_try_codes_str = codes_section.strip()
                    for c in second_try_codes_str.split(","):
                        c_stripped = c.strip()
                        if is_valid_course_code(c_stripped):
                            temp_results.add(c_stripped)
            except IndexError:  # Handle cases where splitting might fail
                pass

        if not temp_results:
            # logger.warning(f"No valid course code found for {code} - {name}")
            pass

        return temp_results
    except Exception as e:
        logger.warning(
            f"Error in determine_course_code for input: code='{code}', name='{name}': {e}"
        )
        return temp_results
