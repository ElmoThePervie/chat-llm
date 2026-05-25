# Chat LLM

ChatGPT-style web app: **FastAPI** backend, **PostgreSQL**, **Redis**, **JWT** auth, **GitHub OAuth**, and a simple **SPA** frontend. Supports mock replies, **Ollama**, or local **GGUF** models.

## What you need

| Tool | Purpose |
|------|---------|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | PostgreSQL + Redis |
| [Python 3.11+](https://www.python.org/downloads/) | Backend API |
| [Ollama](https://ollama.com) | Real local AI without building `llama-cpp-python` |
| [Git](https://git-scm.com/) | Clone this repo |

> **Do not commit** `.env` or large `*.gguf` model files — they are listed in `.gitignore`.

---

## 1. Clone the repository

```bash
git clone https://github.com/ElmoThePervie/chat-llm.git
cd chat-llm
```
---

## 2. Start PostgreSQL and Redis

From the project root:

```bash
docker compose up -d
```

Wait until both containers are healthy (`docker compose ps`).

---

## 3. Backend setup

### Windows (PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Linux / macOS

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Keep this terminal open while using the app.

---

## 4. Configure environment

Edit `backend/.env` (created from `.env.example`):

| Variable | What to set |
|----------|-------------|
| `JWT_SECRET_KEY` | Long random string (required for production) |
| `LLM_MOCK` | `true` = placeholder answers (works immediately) |
| `LLM_BACKEND` | `ollama` |

**GitHub OAuth** (optional): create an app at https://github.com/settings/developers

- Homepage: `http://localhost:8000`
- Callback: `http://localhost:8000/api/auth/github/callback`
- Put **Client ID** and **Secret** in `.env`

---

## 5. Open the app

In your browser go to:

**http://localhost:8000**

1. Register a new account  
2. Click **+** to create a chat  
3. Send a message  

> Always use **http://localhost:8000** (served by uvicorn). Do not open `frontend/index.html` directly.

---

## 6. Real AI replies (optional)

### Ollama (recommended on Windows)

Works even when `llama-cpp-python` fails with CPU errors (`0xc000001d`).

1. Install [Ollama](https://ollama.com) and keep it running.

2. In a **separate terminal** (not inside `.env`):

   ```bash
   ollama pull tinyllama
   ```

3. In `backend/.env`:

   ```env
   LLM_MOCK=false
   LLM_BACKEND=ollama
   OLLAMA_MODEL=tinyllama
   ```

4. Restart uvicorn.



---

## API (summary)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register |
| POST | `/api/auth/login` | Login |
| GET | `/api/chats` | List chats (JWT) |
| POST | `/api/chats/{id}/messages` | Send message |
| POST | `/api/chats/{id}/messages/stream` | Send message (streaming) |

Full list: http://localhost:8000/docs (when server is running).

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `connection refused` (DB) | `docker compose up -d` |
| Network error in browser | Open **http://localhost:8000**; ensure uvicorn is running |
| Error after sending message (stream) | Restart uvicorn after pulling latest code |
| `Failed to load GGUF` / `0xc000001d` | Use `LLM_BACKEND=ollama` + `ollama pull tinyllama` |
| `Cannot connect to Ollama` | Install Ollama, run `ollama pull tinyllama`, keep Ollama running |
| GitHub login 503 | Set `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in `.env` |

---


## License

MIT
