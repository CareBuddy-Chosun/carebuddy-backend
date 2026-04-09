# CareBuddy — Backend

FastAPI-based backend service for CareBuddy, including triage engine, RAG pipeline, and STT/TTS integration.

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL + Redis
- **AI/NLP**: LangChain + OpenAI GPT / LLaMA + FAISS (Vector DB)
- **Voice**: Whisper (STT) + ElevenLabs / Google TTS
- **Infra**: Docker

## Project Structure

```
carebuddy-backend/
├── app/
│   ├── api/            # FastAPI routers / endpoints
│   ├── triage/         # Triage engine & symptom assessment
│   ├── rag/            # LangChain + Vector DB (RAG pipeline)
│   ├── voice/          # STT/TTS integration
│   ├── models/         # SQLAlchemy DB models
│   ├── schemas/        # Pydantic schemas
│   ├── services/       # Business logic
│   └── core/           # Config, security, dependencies
├── tests/
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Getting Started

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/CareBuddy-Chosun/carebuddy-backend.git
cd carebuddy-backend

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your API keys and DB credentials

# 5. Run with Docker
docker-compose up --build

# Or run locally
uvicorn app.main:app --reload
```

### Environment Variables

See `.env.example` for required variables.

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Full API spec: [`carebuddy-docs/api/`](https://github.com/CareBuddy-Chosun/carebuddy-docs)

## Team

| Name | Responsibility |
|------|----------------|
| Jihyuk Lee | Backend architecture, deployment, security |
| Eojin Kim | STT/TTS pipeline, voice data processing |
| Patience | LLM prompting, RAG engineering |
| Muruga | Medical knowledge (ICD-10), embedding, Vector DB |
