import json
from pathlib import Path

from pydantic import ValidationError

from app.services.resume_parser import parse_resume_text
from app.services.resume_evaluation import evaluate_prediction, summarize_evaluation


def main() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "resume_evaluation.json"
    )
    examples = json.loads(fixture_path.read_text(encoding="utf-8"))
    records = []

    for example in examples:
        try:
            extraction = parse_resume_text(example["text"])
        except ValidationError:
            extraction = None

        records.append(
            evaluate_prediction(example["expected"], extraction, example["text"])
        )

    print(json.dumps(summarize_evaluation(records), indent=2))


if __name__ == "__main__":
    main()
