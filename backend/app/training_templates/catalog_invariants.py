from collections.abc import Iterable


def validate_catalog_topology(
    days_per_week: int,
    focus_tags: Iterable[object],
) -> None:
    """Reject catalog shapes that are not credible at their weekly frequency."""
    tag_values = {str(getattr(tag, "value", tag)) for tag in focus_tags}
    structure_tags = tag_values.intersection(
        {"full_body", "upper_lower", "push_pull_legs", "body_part_rotation"}
    )
    if days_per_week >= 4 and structure_tags == {"full_body"}:
        raise ValueError("Pure full-body templates are limited to two or three days per week")
