# Re:Learn Backend

Re:Learn is not a quiz grader. It identifies **why** a Java beginner is wrong, gives a targeted intervention, then asks a **new** question to check whether the misconception is actually resolved.

AI runs on **Groq** (`qwen/qwen3.8-27b` by default). If Groq is down or the key is missing, a local Java misconception catalog still diagnoses the demo.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Put your Groq key in `.env` as `GROQ_API_KEY`. Keep `GROQ_MODEL=qwen/qwen3.8-27b`.

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Docs: http://127.0.0.1:8000/docs  
Demo script: http://127.0.0.1:8000/demo/scenario

Demo login: `demo@relearn.dev` / `demo1234`

SQLite file `relearn.db` is created on first run (gitignored). No Supabase tables are required for the MVP.

## Judge demo (assignment vs comparison)

1. `POST /auth/login` with the demo account.
2. `POST /attempts` with question `q_eq_meaning` and answer `It assigns a value to a variable.`
3. UI should show: incorrect, misconception **Assignment (=) vs comparison (==)**, plus an intervention that does not just dump the answer.
4. `POST /reassessments` with the returned `diagnosis.id` and answer `true` for `If int x = 10, what does x == 10 return?`
5. Status becomes **RESOLVED**. `GET /students/{id}/progress` shows Java Operators improved.

## Frontend contract

Send `Authorization: Bearer <accessToken>` on student routes.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/register` `/auth/login` `/auth/logout` | Auth |
| GET | `/auth/me` | Current student |
| GET | `/questions` `/questions/{id}` | Bank (filter: concept, difficulty, domain, misconception) |
| POST | `/attempts` | Submit answer + reasoning + code; returns diagnosis, learnerView, intervention, next question |
| GET | `/attempts/{id}` | One attempt |
| POST | `/diagnosis` | Same engine as attempts |
| GET | `/misconceptions` `/misconceptions/{id}` | Catalog |
| GET | `/interventions/{diagnosisId}` | Targeted intervention |
| POST | `/reassessments` | New equivalent question result: RESOLVED / NOT_RESOLVED / UNCERTAIN |
| GET | `/students/{id}/progress` | Dashboard |
| GET | `/students/{id}/misconceptions` | active / resolved / recurring |
| GET | `/students/{id}/recommendations` | Next best activity |
| GET | `/students/{id}/history` | Misconception timeline |
| POST | `/evaluation/run` | Labeled-set accuracy / precision / recall / F1 |

Legacy `POST /analyze` still works for older UI code.

`POST /attempts` is the important payload: the frontend can drive the whole Re:Learn loop from that one response.

## Layout

```
main.py            FastAPI app
app/config.py      env
app/models.py      learner model schema
app/catalog.py     10 Java misconceptions + questions
app/services/      diagnosis, intervention, resolution, recommendations
app/routers/       HTTP API
```

AI keys never leave the backend. Passwords are PBKDF2 hashes, not plaintext.
