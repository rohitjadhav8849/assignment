from app.database.session import SessionLocal
from app.services.job_embeddings import index_jobs


def main() -> None:
    with SessionLocal() as session:
        summary = index_jobs(session)

    print(
        f"Job indexing: {summary.total_jobs} processed, "
        f"{summary.successful} successful, {summary.failed} failed, "
        f"{summary.upserted} upserted, {summary.unchanged} unchanged."
    )
    for error in summary.errors:
        print(error)
    if summary.failed or summary.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
