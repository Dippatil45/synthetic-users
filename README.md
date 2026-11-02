# Synthetic User Generation Platform

A FastAPI backend that generates realistic virtual user personas with Generative AI, enabling product teams to run simulated interviews and tests before talking to real users.

**Status:** Milestone 1 complete.

## How It Works

Demographics and behavior are sampled in code from weighted distributions, ensuring diversity and reproducibility with a seed. The Gemini LLM only writes the persona's name and backstory based on the sampled attributes, keeping generation fast and deterministic where it matters.

## Tech Stack

- Python 3.11
- FastAPI
- Pydantic v2
- SQLAlchemy 2.0
- SQLite
- httpx
- pytest
- Gemini API

## Setup (Windows PowerShell)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
DATABASE_URL=sqlite:///./personas.db
LLM_API_KEY=your_gemini_api_key
LLM_MODEL=gemini-3.5-flash-lite
```

**Important:** Never commit `.env` or share your API key.

## Run

```powershell
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs for interactive API documentation.

## Quick Demo

1. **Generate 10 personas:** `POST /personas/generate?count=10`
2. **Enrich with LLM:** `POST /personas/enrich-pending?limit=5`
   - Free tier is rate limited, so run in batches of 5 and wait a minute between batches
3. **List personas:** `GET /personas`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/personas` | Create a persona |
| GET | `/personas` | List personas (filters: status, tag, limit, offset) |
| GET | `/personas/{id}` | Get persona by ID |
| PATCH | `/personas/{id}` | Update persona |
| DELETE | `/personas/{id}` | Delete persona |
| POST | `/personas/generate` | Generate synthetic personas (count 1-100, optional seed) |
| POST | `/personas/{id}/enrich` | Enrich single persona with LLM |
| POST | `/personas/enrich-pending` | Batch enrich personas without backstory |

## Rules

**Status Transitions:**
- draft → active ✓
- draft → archived ✓
- active → archived ✓
- archived → active ✓
- Any other transition returns 409

**Versioning:**
Version increments only when demographics, professional, behavioral, psychological, or backstory change. Updating name, tags, or status does not change version.

## Project Structure

```
app/
├── main.py                    # FastAPI app
├── config.py                  # Settings
├── db.py                      # Database setup
├── models/persona.py          # SQLAlchemy model
├── schemas/persona.py         # Pydantic schemas
├── generation/
│   ├── distributions.py       # Weighted distributions
│   └── sampler.py            # Profile sampling logic
├── llm/
│   ├── client.py             # Gemini API client
│   └── persona_writer.py     # Identity generation
└── routers/
    └── personas.py           # API endpoints

tests/                        # 13 tests
```

## Tests

```powershell
python -m pytest -q
```

All 13 tests pass. API tests use an in-memory database and LLM tests use mocks (no real API calls during testing).

## Known Limitations

- Distribution weights are assumptions, not based on census data
- Free-tier LLM rate limits require batching enrichment requests
- LLM-generated text may carry societal stereotypes
- SQLite is suitable for prototypes, not production scale

## Roadmap

**Milestone 2:** Psychological profiles, interviews and surveys, persona memory

**Milestone 3:** Product testing and journey simulation

**Milestone 4:** Analytics dashboard and reports
