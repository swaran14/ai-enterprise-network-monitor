import difflib


def compare_configurations(old_config: str, new_config: str):
    """
    Compare two network-device configurations.

    Returns whether a change was detected,
    a readable summary, and the configuration diff.
    """

    old_config = old_config or ""
    new_config = new_config or ""

    # Normalize lines to reduce meaningless whitespace differences
    old_lines = [
        line.rstrip()
        for line in old_config.strip().splitlines()
    ]

    new_lines = [
        line.rstrip()
        for line in new_config.strip().splitlines()
    ]

    if old_lines == new_lines:
        return {
            "change_detected": False,
            "summary": "No configuration changes detected.",
            "added_lines": 0,
            "removed_lines": 0,
            "diff": []
        }

    diff = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="previous_configuration",
            tofile="current_configuration",
            lineterm=""
        )
    )

    added_lines = sum(
        1
        for line in diff
        if line.startswith("+") and not line.startswith("+++")
    )

    removed_lines = sum(
        1
        for line in diff
        if line.startswith("-") and not line.startswith("---")
    )

    summary = (
        f"Configuration change detected: "
        f"{added_lines} line(s) added and "
        f"{removed_lines} line(s) removed."
    )

    return {
        "change_detected": True,
        "summary": summary,
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "diff": diff
    }