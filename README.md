# Re:Learn Backend

FastAPI service for the Re:Learn misconception detection system. It uses Gemini 1.5 Flash to diagnose the student's thinking error (not just right/wrong) and stores sessions in Supabase.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill `.env` with:

- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

## Run

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://127.0.0.1:8000/docs

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| POST | `/analyze` | Diagnose misconception from question + answers |
| POST | `/save-session` | Persist an analysis result to Supabase |
| GET | `/sessions` | List sessions, including `resolved` status |
| PATCH | `/sessions/{id}/resolve` | Mark a misconception as resolved |

`POST /analyze` body:

```json
{
  "question": "What does 2 + 3 * 4 equal in Python?",
  "student_answer": "20",
  "correct_answer": "14",
  "domain": "programming"
}
```

Response:

```json
{
  "misconception_type": "Operator Precedence Confusion",
  "confidence": 0.92,
  "explanation": "...",
  "intervention": "...",
  "is_correct": false
}
```

## Supabase table

Create a `sessions` table (SQL editor):

```sql
create table if not exists sessions (
  id uuid primary key default gen_random_uuid(),
  question text not null,
  student_answer text not null,
  correct_answer text not null,
  domain text not null default 'programming',
  misconception_type text not null,
  confidence double precision not null,
  explanation text not null,
  intervention text not null,
  is_correct boolean not null,
  resolved boolean not null default false,
  created_at timestamptz not null default now()
);
```

Enable insert/select/update for the key you put in `SUPABASE_KEY`.
