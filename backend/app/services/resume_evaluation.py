import re
from collections import defaultdict
from typing import Any

from app.schemas.resumes import ResumeExtraction
from app.services.resume_validation import validate_extraction

_LIST_FIELDS = (
    "skills",
    "education",
    "work_experience",
    "projects",
    "certifications",
)
_SCALAR_FIELDS = (
    "full_name",
    "email",
    "phone",
    "total_experience_years",
)


def _normalize(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return format(float(value), ".15g")
    return re.sub(r"\s+", " ", str(value)).casefold().strip()


def _predicted_facts(extraction: ResumeExtraction, field: str) -> set[str]:
    if field in _SCALAR_FIELDS:
        fact = getattr(extraction, field)
        if fact is None:
            return set()
        value = fact.value if hasattr(fact, "value") else fact
        return {_normalize(value)}
    if field == "skills":
        values = [item.name for item in extraction.skills]
    elif field == "education":
        values = [
            item.degree or item.institution or item.field_of_study
            for item in extraction.education
        ]
    elif field == "work_experience":
        values = [item.title for item in extraction.work_experience]
    elif field == "projects":
        values = [item.name for item in extraction.projects]
    elif field == "certifications":
        values = [item.name for item in extraction.certifications]
    else:
        raise ValueError(f"Unsupported evaluation field: {field}")
    return {_normalize(value) for value in values if value}


def _expected_facts(expected: dict[str, Any], field: str) -> set[str]:
    if field in _SCALAR_FIELDS:
        value = expected.get("fields", {}).get(field)
        return set() if value is None else {_normalize(value)}
    return {
        _normalize(value)
        for value in expected.get(field, [])
        if value is not None and str(value).strip()
    }


def _fact_counts(expected: set[str], predicted: set[str]) -> dict[str, int | float]:
    true_positive = len(expected & predicted)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)
    precision = true_positive / (true_positive + false_positive) if predicted else 0.0
    recall = true_positive / (true_positive + false_negative) if expected else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "exact": int(expected == predicted),
    }


def evaluate_prediction(
    expected: dict[str, Any],
    extraction: ResumeExtraction | None,
    source_text: str,
) -> dict[str, Any]:
    fields = (*_SCALAR_FIELDS, *_LIST_FIELDS)
    field_metrics = {
        field: _fact_counts(
            _expected_facts(expected, field),
            _predicted_facts(extraction, field) if extraction is not None else set(),
        )
        for field in fields
    }
    validation = (
        validate_extraction(extraction, source_text)
        if extraction is not None
        else {
            "supported_claim_count": 0,
            "claim_count": 0,
            "unsupported_claim_count": 0,
        }
    )
    skills = field_metrics["skills"]
    contact_fields = ("full_name", "email", "phone")
    return {
        "field_metrics": field_metrics,
        "skill_true_positive": skills["true_positive"],
        "skill_false_positive": skills["false_positive"],
        "skill_false_negative": skills["false_negative"],
        "contact_field_correct": sum(field_metrics[field]["exact"] for field in contact_fields),
        "contact_field_count": len(contact_fields),
        "supported_claim_count": validation["supported_claim_count"],
        "claim_count": validation["claim_count"],
        "unsupported_claim_count": validation["unsupported_claim_count"],
        "incorrect_fact_count": sum(
            int(metrics["false_positive"]) for metrics in field_metrics.values()
        ),
        "structured_output_validation_failures": int(extraction is None),
    }


def summarize_evaluation(records: list[dict[str, Any]]) -> dict[str, Any]:
    fields: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "true_positive": 0,
            "false_positive": 0,
            "false_negative": 0,
            "exact": 0,
            "count": 0,
        }
    )
    totals = {
        key: sum(int(record[key]) for record in records)
        for key in (
            "supported_claim_count",
            "claim_count",
            "unsupported_claim_count",
            "incorrect_fact_count",
            "structured_output_validation_failures",
            "contact_field_correct",
            "contact_field_count",
        )
    }
    for record in records:
        for field, metrics in record["field_metrics"].items():
            for key in ("true_positive", "false_positive", "false_negative", "exact"):
                fields[field][key] += int(metrics[key])
            fields[field]["count"] += 1

    def ratio(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 4) if denominator else 0.0

    skill = fields["skills"]

    def field_summary(counts: dict[str, int]) -> dict[str, int | float]:
        precision = ratio(
            counts["true_positive"],
            counts["true_positive"] + counts["false_positive"],
        )
        recall = ratio(
            counts["true_positive"],
            counts["true_positive"] + counts["false_negative"],
        )
        return {
            "precision": precision,
            "recall": recall,
            "f1": ratio(2 * precision * recall, precision + recall),
            "exact_accuracy": ratio(counts["exact"], counts["count"]),
            "true_positive": counts["true_positive"],
            "false_positive": counts["false_positive"],
            "false_negative": counts["false_negative"],
        }

    return {
        "resume_count": len(records),
        "skill_precision": field_summary(skill)["precision"],
        "skill_recall": field_summary(skill)["recall"],
        "skill_f1": field_summary(skill)["f1"],
        "field_metrics": {
            field: field_summary(counts)
            for field, counts in sorted(fields.items())
        },
        "field_level_accuracy": ratio(
            sum(counts["exact"] for counts in fields.values()),
            sum(counts["count"] for counts in fields.values()),
        ),
        "contact_information_accuracy": ratio(
            totals["contact_field_correct"], totals["contact_field_count"]
        ),
        "evidence_coverage": ratio(
            totals["supported_claim_count"], totals["claim_count"]
        ),
        "unsupported_claim_rate": ratio(
            totals["unsupported_claim_count"], totals["claim_count"]
        ),
        "incorrect_fact_count": totals["incorrect_fact_count"],
        "structured_output_validation_failure_rate": ratio(
            totals["structured_output_validation_failures"], len(records)
        ),
        "counts": totals,
    }
