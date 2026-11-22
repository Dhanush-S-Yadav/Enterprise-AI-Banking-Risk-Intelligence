# Enterprise AI Banking Knowledge & Risk Intelligence Assistant

**A local Windows 11, evidence-grounded banking knowledge prototype using Advanced RAG + 5 LangGraph agents.**

> **SYNTHETIC ACADEMIC DEMO.** All bundled policies, cases, amounts, thresholds, and organizations are fictional. The application is not a bank core system, automated loan decision tool, fraud detector, legal authority, or production security/compliance platform. Do not upload actual customer data.

## What is included

- **FastAPI backend:** JWT login, role-based access enforcement, document management, search, agent routing, conversation history, reports, audit and feedback APIs; interactive Swagger at `http://localhost:8000/docs`.
- **Advanced retrieval:** local SentenceTransformers BGE embeddings, Chroma vector search, BM25 keyword retrieval, deterministic banking query expansion/multi-query search, Reciprocal Rank Fusion, cross-encoder reranking, contextual sentence compression, and parent-child document chunks with source IDs.
- **5 LangGraph agents:** banking document Q&A, compliance checklist, fraud/risk incident briefing, policy comparison, report synthesis. Explicit evidence validation and separate agent behavior.
- **React / Vite / Material UI / Recharts frontend:** login, real dashboard, chat, drag/drop library, policy comparison, compliance, fraud & risk, PDF reports and administration.
- **24 bundled synthetic text documents** covering lending, KYC, AML, compliance, fraud, operational risk, cybersecurity, data privacy, audit and governance, including two credit risk policy versions.
- **Local-only persistence:** JSON (users, conversations, feedback, audit, documents/chunk metadata, reports), local source files and PDFs, plus Chroma vector index. **No application-level SQL or relational database.** Chroma manages its own implementation internals.
- **Secure defaults for an academic demonstration:** Argon2 hashes, signed JWT, no token/credential auditing, per-route server-side authorization, local-loopback hosting and PDF ownership checks. Not security-hardened for production.

## Windows 11 installation

### Prerequisites

1. Install **Python 3.11** (enable Python launcher `py`) and **Node.js LTS**.
2. Install **Ollama for Windows** from <https://ollama.com/download/windows> and ensure it is running.
3. Open **PowerShell** in the extracted project directory (e.g., `C:\BankingAI`).

### Commands

```powershell
# In the project root:
.\scripts\setup_windows.ps1
ollama pull llama3.1:8b

# Terminal 1, from project root:
.\scripts\start_backend.ps1

# Terminal 2, from project root:
.\scripts\start_frontend.ps1
```

Open **http://localhost:5173**. In Document Library, choose **Load 24 demo documents** (one-time indexing; the first run downloads the BGE embedding and reranking models). Test an evidence-grounded question in AI Banking Assistant. `http://localhost:8000/docs` lists all APIs. Backend index failures are shown on each document's status row.

If PowerShell blocks local scripts, use `powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1` or run the underlying Python/npm commands; avoid permanently lowering system policy.

### Install manually (no PowerShell script)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
cd frontend
npm install
cd ..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
# in another terminal:
cd frontend
npm run dev
```

### Model and hardware notes

Default model **`llama3.1:8b`** is the exact 8B model requested. It takes multiple gigabytes of RAM and disk. If the laptop cannot run it, the app lets you change `.env` to `OLLAMA_MODEL=llama3.2:1b` after running `ollama pull llama3.2:1b`. This **changes the LLM from the requested 8B model** but preserves the local architecture. Restart the backend afterward. The embedding and cross-encoder models are downloaded once from Hugging Face by SentenceTransformers; an internet connection is needed for that first run, not for subsequent offline queries. No OpenAI API key is needed.

`OLLAMA_URL` defaults to `http://127.0.0.1:11434`; errors are surfaced to the browser if Ollama is stopped or the model is missing.

### Demo users

All demo accounts initially use password **`Demo@12345`**. Their user accounts are created on first backend startup and stored as Argon2 password hashes inside `data/users.json` (the plaintext password is never written there). Credentials are intended **only for isolated local testing**. Change `DEMO_PASSWORD` in `.env` **before first startup** to seed another shared password. To reset a demo-only instance, stop both servers and delete the local `data` directory (this irreversibly deletes your local documents/index/history/reports).

| Username | Role | Capabilities |
|---|---|---|
| `service` | Customer Service Executive | Chat, search, view docs |
| `loan` | Loan Officer | Chat, search, upload, reports |
| `compliance` | Compliance Officer | Compliance, compare, upload, delete |
| `risk` | Risk Analyst | Fraud/risk, compare, upload |
| `manager` | Branch Manager | All business agents, reports |
| `auditor` | Auditor | Read-only docs, compare, compliance, reports |
| `admin` | Administrator | All functions, audit logs, users |

Public registration is constrained server-side to the Customer Service Executive role. The system does not allow self-registration as an administrator.

## API summary

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| Chat | `POST /api/chat`, `GET/DELETE /api/chat/history` |
| Documents | `POST /api/documents/upload`, `GET /api/documents`, `GET/DELETE /api/documents/{document_id}`, `POST /api/documents/reindex`, `POST /api/documents/seed-demo` |
| Retrieval | `POST /api/search`, `GET /api/search/filters` |
| Agents | `POST /api/agents/route`, `/api/agents/compare-policies`, `/api/agents/compliance-checklist`, `/api/agents/fraud-summary` |
| Reports | `POST /api/reports/generate`, `GET /api/reports`, `GET /api/reports/{report_id}/download` |
| Admin | `GET /api/admin/dashboard`, `GET /api/admin/users`, `PATCH /api/admin/users/{user_id}`, `GET /api/admin/audit-logs` |
| Other | `GET /api/dashboard`, `GET /api/health`, `POST /api/feedback` |

## Advanced RAG and agent flow

```text
Upload → format/size/hash validation → text/page extraction → metadata and heading detection
       → recursive parent chunks → recursive child chunks → BGE embeddings
       → ChromaDB and JSON metadata storage

Question → rules-based intent routing → query variants → parallel-type vector + BM25 searches
         → RRF fusion → metadata filter → cross-encoder reranking
         → parent-context expansion → sentence-level compression → vetted citations
         → dedicated LangGraph agent → Ollama Llama 3.1 8B → answer + source cards
```

The policy comparison page uses a **deterministic two-document sentence diff** and source passage cards instead of asking a language model to invent changes. Compliance and fraud agents use separate evidence-restricted prompts. The report agent creates a PDF with documented evidence and prominent limitations. Search may use BM25 as a fallback if the reranker cannot initialize; a successful response should still be reviewed for relevance. If documents do not provide sufficient evidence, the assistant states that explicitly.

### Storage and privacy

- `data/documents/`: source files identified by UUID.
- `data/vectors/`: persistent Chroma collection.
- `data/chunks.json` and `data/parents.json`: chunk metadata and parent text.
- `data/users.json`, `data/conversations.json`, `data/audit.json`, `data/feedback.json`, `data/reports.json`: local application records.
- `data/reports/`: generated PDFs.
- `data/jwt.secret`: generated random JWT signing secret if `JWT_SECRET_KEY` is not set.

Files stay on the local device. Do not put the `data/` folder in source control. This prototype does not encrypt JSON stores at rest, guard against cross-process concurrent modifications, perform malware scanning, extract scanned PDF images using OCR, or satisfy actual banking production controls.

## Developer tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm run build
```

Python tests include source-dataset validation, metadata extraction, Argon2 password checks, role permissions, JSON persistence, query expansion, PDF output, and API authentication checks. The comprehensive quality of LLM answers needs separate manual evaluation with a running Ollama instance and indexed documents.

## Optional Docker (local only)

`docker compose up --build` serves localhost ports 8000/5173. Ollama stays installed on the Windows host; Docker accesses it via `host.docker.internal`. Some Ollama configurations need the host service bound for Docker access; **direct Windows setup is recommended**. Local Docker must not be interpreted as a public cloud deployment.

## Limitations

- Software project code is provided, but production security, bank-grade tenancy, penetration testing, formal compliance validation, and real fraud detection are explicitly out of scope.
- Citations and metadata derive only from actual indexed passages. In DOCX/XLS/TXT sources, page numbers are not available and are left blank rather than invented.
- Hybrid search result quality is probabilistic; reviewer verification is essential.
- Optional cross-encoder model unavailability causes an RRF-only ranking fallback; model setup problems otherwise yield visible errors.
- The uploaded project specification ended partway through the synthetic-document list; the 24-document dataset fulfills the explicit minimum and named topics visible in the specification.

## License notes

This source project is for local academic demonstration. Third-party package/model licenses apply separately; notably, Meta Llama 3.1 is open-weight rather than OSI open source. See its license before distribution or commercial use. No Meta model weights are bundled in the ZIP.
