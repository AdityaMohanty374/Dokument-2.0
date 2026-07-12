# Dokument — PDF Intelligence

Upload a PDF, get an instant AI-generated summary, and keep chatting about
the document afterward — with full conversation history, multiple
conversations per user, and Google sign-in.

## How it works

```
Sign in with Google
        ↓
Upload a PDF ──→ extract text (PyMuPDF) ──→ store original in Cloudflare R2
        ↓
Summarize ──→ Groq (Llama 3.1 8B) streams a summary back token-by-token
        ↓
Keep chatting ──→ each message is saved, full thread history sent to the
                   model on every turn, response streamed back live
```

Conversations, messages, and uploaded documents all persist per-user in
Postgres, so you can close the tab and pick a conversation back up later.

## Features

- **Google OAuth sign-in** — no passwords, JWT session tokens issued after login
- **PDF upload + summarization** — text extracted server-side, summarized by an LLM
- **Streaming chat** — ask follow-up questions about the uploaded document; responses stream token-by-token instead of waiting for the full answer
- **Multiple conversations** — create, switch between, and delete conversations independently, each with its own uploaded document and message history
- **Auto-titling** — a conversation's placeholder title is replaced automatically with the PDF's filename (or the first message, if no PDF yet) the first time there's something meaningful to name it after
- **Persistent storage** — conversations/messages in Postgres, original PDFs in Cloudflare R2 (S3-compatible object storage)

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python) |
| LLM | Groq API, Llama 3.1 8B Instant (OpenAI-compatible client) |
| PDF text extraction | PyMuPDF (`fitz`) |
| Database | Postgres (Neon) via SQLAlchemy |
| Object storage | Cloudflare R2 (S3-compatible) — stores the original uploaded PDFs |
| Auth | Google OAuth 2.0 → signed JWT session tokens |
| Frontend | Static HTML/CSS/JS, served separately (e.g. Vercel) |

## Project structure

```
backend/
  main.py        FastAPI app — auth routes, conversation CRUD, /chat, /upload
  auth.py         Google OAuth flow, JWT issuing/verification, current-user dependency
  llm.py          Groq streaming client, PDF text extraction, prompt helpers
  storage.py      Cloudflare R2 upload/delete for original PDF files
  database.py     SQLAlchemy engine/session setup
  models.py       User, Conversation, Message, Document ORM models
  schemas.py      Pydantic request/response schemas
  prompts.py      System prompt used for chat/summarization
  config.py       Env-based settings (DB, JWT, OAuth, R2 credentials)
  requirements.txt
frontend/
  index.html      Single-file UI — login gate, conversation sidebar, chat pane
```

## Setup

```bash
cd backend
pip install -r requirements.txt
```

### Required environment variables

```bash
# Database (Neon Postgres, or any Postgres instance)
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require

# JWT session tokens
JWT_SECRET=some_long_random_secret

# Google OAuth — create credentials at https://console.cloud.google.com
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=https://your-backend-url/auth/google/callback

# Where the browser gets sent after login completes
FRONTEND_URL=https://your-frontend-url

# Cloudflare R2 (S3-compatible object storage)
R2_ACCOUNT_ID=your_r2_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=your_bucket_name

# Groq (LLM)
GROQ_API_KEY=your_groq_key
```

### Run locally

```bash
uvicorn main:app --reload --port 8000
```

Serve `frontend/index.html` separately (or open it directly, pointed at your
local backend URL) — the frontend and backend are deployed independently in
this project (unlike a single combined FastAPI + StaticFiles setup).

## Deployment

- **Backend**: Render (or any host that supports a long-running Python
  process — this isn't serverless-friendly, since it holds a DB connection
  pool and streams responses)
- **Frontend**: Vercel (or any static host) — just update the base URL the
  frontend points to for your API

### Google OAuth — publishing status

While your OAuth consent screen is in **"Testing"** mode, only Google
accounts explicitly added as test users can sign in (up to 100). Anyone else
gets blocked at Google's login screen. To let anyone sign in, move the
consent screen to **Production** — this may require Google's app
verification process if you request sensitive scopes (this app only
requests `openid email profile`, which are non-sensitive, so verification
requirements should be minimal, but confirm in Google Cloud Console).

## Known limitations

- **No rate limiting** — any authenticated user can call `/chat` and
  `/upload` as often as they want, which directly consumes your Groq quota.
  Worth adding per-user request limits before sharing this publicly.
- **No file size/type validation beyond `.pdf` extension check** — a
  maliciously named non-PDF file would fail at the text-extraction step
  rather than being rejected upfront.
- **Single JWT secret, no refresh tokens** — sessions are valid for a fixed
  duration (14 days) with no revocation mechanism short of rotating
  `JWT_SECRET` (which invalidates every active session at once).
- **No streaming cancellation** — once a `/chat` or `/upload` response
  starts streaming, there's no way for the client to cancel it server-side;
  closing the tab just stops reading the stream, the backend still finishes
  generating and writes the full response to the database.
