# BookMore

BookMore is a local job-discovery project I built to compare profile-based
matching with keyword and semantic job retrieval. It lets a candidate review a
resume-derived profile and explore a set of synthetic job listings. The scores
are useful for comparing results in this demo; they are not hiring
probabilities.

## Main features

- Upload a PDF resume and extract structured details locally with PyMuPDF and
  Python parsing. Scanned PDFs are reported as unsupported because OCR is not
  included.
- Review, edit, and confirm extracted candidate information before it is used
  in the profile.
- Browse job details and personalized Picks using the existing deterministic
  candidate-to-job matching score.
- Compare four ranking modes on Picks: Original Picks, BM25, Semantic, and
  Hybrid.
- Use BM25 keyword retrieval, dense semantic retrieval, or both combined with
  Reciprocal Rank Fusion (RRF). Scores use different scales, so compare
  rankings within a mode rather than comparing raw scores across modes.
- Save job-search preferences such as roles, locations, work modes, and
  employment types.

## Tech stack

- Frontend: React, Vite, JavaScript, and CSS.
- Backend: Python, FastAPI, Pydantic Settings, SQLAlchemy 2, and Alembic.
- Data: PostgreSQL for jobs, profiles, and resume records; Qdrant for the job
  vector index.
- Local processing: PyMuPDF for PDF text extraction and
  `sentence-transformers/all-MiniLM-L6-v2` for job and query embeddings.
- Tests: Pytest, with SQLite and in-memory Qdrant used by the automated tests.

## Architecture and request flow

The React app calls the FastAPI backend. PostgreSQL is the source of truth for
job and candidate data. The original Picks endpoint reads those records and
uses the existing matching service.

For BM25, Semantic, and Hybrid retrieval, the backend builds one search query
from available candidate skills, roles, experience, projects, and work
history. Contact details are not part of this query. BM25 ranks the stored job
text, Semantic embeds the query and searches the existing Qdrant `jobs`
collection, and Hybrid combines the two ranked lists with RRF. Job embeddings
are indexed from PostgreSQL `searchable_text`; Qdrant is a search index, not
the source of truth.

Resume PDFs are stored in the local `storage/resumes/` directory, outside the
frontend. FastAPI extracts their text and runs the local parser in a
background task. The candidate can review the result before confirming it.
Resume contents are not sent to an LLM. The Sentence Transformers model files
are downloaded and cached locally on first use; query and job embeddings are
then generated locally.

## Project structure

```text
backend/
  alembic/             Database migrations
  app/
    api/               FastAPI routes
    core/              Application settings
    database/          SQLAlchemy session setup
    models/            Job, candidate, and resume models
    schemas/           API request and response schemas
    services/          Matching, retrieval, indexing, and resume parsing
    main.py            FastAPI application
    seed_jobs.py       Synthetic job seeding and indexing
  tests/               Backend tests and synthetic resume fixtures
frontend/
  src/
    components/        Shared layout and UI components
    pages/             Chat, Picks, Tracker, Resumes, and Your Search
    services/          Frontend API calls
docker-compose.yml     Local PostgreSQL and Qdrant services
.env.example           Safe example configuration
```

The Chat page is currently a frontend workspace; there is no chatbot or LLM
backend.

## Requirements

- Windows PowerShell
- Python 3.11 or newer
- Node.js and npm
- Docker Desktop with Docker Compose

## Local setup on Windows

Run commands from the repository root unless a step says otherwise.

### Configure the environment and start data services

Create a local `.env` from the example if one does not already exist:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

The example is for local development. Docker Compose reads `POSTGRES_USER`,
`POSTGRES_PASSWORD`, and `POSTGRES_DB`; the backend reads `DATABASE_URL` and
`QDRANT_URL` from the same root `.env`. Keep the PostgreSQL credentials in
`DATABASE_URL` consistent with the `POSTGRES_*` values. Leave
`QDRANT_API_KEY` blank for the local Compose service unless you have configured
Qdrant authentication.

Start PostgreSQL and Qdrant:

```powershell
docker compose up -d postgres qdrant
docker compose ps
```

PostgreSQL is available locally on port `5433`; Qdrant's HTTP API is on port
`6333`. Compose uses named volumes to retain their data. To stop the services
without deleting that data, run `docker compose down`. Avoid `docker compose
down -v` unless you intend to remove the volumes.

### Install, migrate, and seed the backend

In a new PowerShell terminal:

```powershell
Set-Location .\backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m app.seed_jobs
```

The seed command creates or updates 300 synthetic jobs in PostgreSQL and then
indexes their searchable text in Qdrant. It uses the same job IDs when it
updates seeded records. The first indexing run downloads the embedding model
if it is not already cached. To refresh the Qdrant index after job changes
made outside the seed command, run `python -m app.index_jobs` from `backend/`.

### Run the backend

From the backend terminal:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The API is at `http://127.0.0.1:8000`; interactive documentation is at
`http://127.0.0.1:8000/docs`. `GET /health` checks that the API process is
running. `GET /ready` reports PostgreSQL and Qdrant availability.

### Run the frontend

In another PowerShell terminal:

```powershell
Set-Location .\frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/`.

### Environment variables

`.env.example` lists the settings recognized by the project. The main groups
are:

- PostgreSQL connection settings: `DATABASE_URL` and the Compose
  `POSTGRES_*` values.
- Qdrant connection settings: `QDRANT_URL` and optional `QDRANT_API_KEY`.
- Resume storage and limits: `RESUME_STORAGE_DIR`,
  `RESUME_PROCESSING_STALE_SECONDS`, and the `MAX_RESUME_*` values.
- Browser access: `CORS_ORIGINS`.
- Original matching weights: `MATCH_WEIGHT_*`.

Use your own local `.env`, do not put real credentials in `.env.example`, and
do not commit `.env`. Resume storage defaults to `storage/resumes/` and is
excluded by `.gitignore`.

## Tests and evaluation

Run the backend tests from `backend/`:

```powershell
python -m pytest
```

The automated tests use an isolated SQLite database and in-memory Qdrant for
fast coverage. They do not prove that your local PostgreSQL or Docker Qdrant
services are running; use `/ready` to check those services.

The offline resume evaluation uses only synthetic fixtures:

```powershell
python -m app.evaluate_resumes
```

Its results describe the included fixtures only and should not be read as
general resume-parsing accuracy.

Build the frontend for production from `frontend/`:

```powershell
npm run build
```

## Current limitations and possible next steps

- The job listings are synthetic; there is no external job ingestion yet.
- BM25 currently reads job text payloads from Qdrant and calculates scores in
  the backend. This is straightforward for the demo collection but will need
  a more scalable approach as the index grows.
- Removed jobs are not automatically deleted from Qdrant. Re-run the indexer
  after job updates; deletion synchronization is not implemented.
- Resume extraction does not support OCR for scanned PDFs.
- The app has one shared candidate profile and no sign-in or per-user access
  control. It is intended for local development, not an untrusted network.
- Resume files and extracted text are stored locally and are not encrypted at
  rest.
- The Chat page has no assistant service, and job ingestion, authentication,
  OCR, and multi-user support remain future work.
