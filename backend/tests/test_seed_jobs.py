from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

from app.models.job import Job
from app.seed_jobs import seed_jobs_into


def test_seed_is_synthetic_and_repeatable() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        assert seed_jobs_into(engine) == (300, 0)
        assert seed_jobs_into(engine) == (0, 300)

        with engine.connect() as connection:
            count = connection.scalar(select(func.count()).select_from(Job))
            synthetic_count = connection.scalar(
                select(func.count()).select_from(Job).where(
                    Job.is_synthetic.is_(True),
                    Job.data_source == "SYNTHETIC DEMO",
                )
            )

        assert count == 300
        assert synthetic_count == 300
    finally:
        engine.dispose()
