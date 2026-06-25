# ERP AI SQL Assistant

AI-powered Text-to-SQL assistant and metadata-driven data entry tool for Sage 100 / SQL Server databases.

Ask questions in natural language like:

- "Show all customers"
- "Top invoices this month"
- "List payment methods"
- "Show products with low stock"

Or use the **Data Entry** UI to create and update records directly — with schema-driven forms, validation, SQL preview, and confirmation before any write touches the database.

The system retrieves relevant schema context using semantic search (FAISS + embeddings), generates SQL with an LLM, validates it against the REAL database schema, then executes it safely.

---

# Features

## AI Text-to-SQL
Convert natural language into SQL Server T-SQL queries.

## RAG-based Schema Retrieval
Uses semantic embeddings to retrieve only the most relevant tables and columns for the prompt.

## Real Database Validation
Generated SQL is validated against the live SQL Server schema before execution.

## Self-Correction Loop
If SQL execution fails, the AI automatically retries with the database error message.

## Metadata-Driven Data Entry
Create and update records through a dynamic form UI — no raw SQL, no guesswork:
- Table selector backed by the live database schema
- Forms auto-generated from `INFORMATION_SCHEMA` column metadata
- Required fields highlighted, identity/computed columns locked read-only
- Full validation before any write: table exists, columns exist, required fields provided, types checked
- SQL preview with confirmation modal before execution
- Parameterized queries only — no string concatenation, no SQL injection surface
- Session history log of all executed operations

## FastAPI REST API
Expose the assistant over HTTP for dashboards and frontend apps.

## JWT Authentication & Role-Based Access
- `/ask` and read endpoints: any authenticated user
- Data Entry preview: any authenticated user
- Data Entry execute + admin routes: admin role only

## SQL Injection & Dangerous Query Protection
Blocks on the read pipeline:
- DROP, DELETE, UPDATE, INSERT, EXEC, XP_*, OPENROWSET, and more

Write pipeline uses structured actions (never raw LLM SQL) + parameterized execution.

---

# Architecture

## Read Pipeline (Ask)

```text
User Question
      ↓
Schema Retrieval (FAISS + Embeddings)
      ↓
Prompt Builder
      ↓
LLM → SQL Generation
      ↓
SQL Validator
      ↓
SQL Server Execution
      ↓
Results Returned
```

## Write Pipeline (Data Entry)

```text
User selects table
      ↓
GET /tables/{name}/metadata  (INFORMATION_SCHEMA + COLUMNPROPERTY)
      ↓
Dynamic form rendered in browser
      ↓
User fills form → POST /records/create  or  /records/update
      ↓
Server validates (table whitelist, column existence, required fields, types)
      ↓
Preview returned with generated SQL (parameterized)
      ↓
User confirms → POST /records/execute  (admin only)
      ↓
Parameterized INSERT / UPDATE via SQLAlchemy transaction
      ↓
Rows affected + duration returned
```

---

# API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | public | Register a new user |
| POST | `/auth/login` | public | Login, get JWT |
| GET | `/auth/me` | any | Current user info |
| POST | `/ask` | any | Natural-language SQL query |
| POST | `/intent` | any | Classify question intent |
| GET | `/tables` | any | List all database tables |
| GET | `/tables/{name}/metadata` | any | Column metadata for a table |
| POST | `/records/create` | any | Validate + preview an INSERT |
| POST | `/records/update` | any | Validate + preview an UPDATE |
| POST | `/records/execute` | admin | Execute a confirmed write |
| POST | `/write/preview` | any | NLP-driven write preview |
| POST | `/write/execute` | admin | NLP-driven write execute |
| POST | `/erp/write/preview` | any | ERP entity-aware write preview |
| POST | `/erp/write/execute` | admin | ERP entity-aware write execute |
| GET | `/health` | admin | Backend health check |
| GET | `/schema-tables` | admin | FAISS-indexed table list |
| POST | `/rebuild` | admin | Rebuild FAISS schema index |

---

# Project Structure

```
erp-ai-sql-assistant/
├── api/
│   ├── app.py                  # FastAPI app, router mounting, existing endpoints
│   ├── metadata_router.py      # GET /tables, GET /tables/{name}/metadata
│   └── records_router.py       # POST /records/create|update|execute
├── core/
│   ├── agent.py                # Read pipeline (ERPAgent)
│   ├── write_agent.py          # NLP write pipeline (WriteAgent)
│   ├── db.py                   # SQLAlchemy engine, run_query, run_write
│   └── llm.py                  # Groq LLM client
├── erp/
│   ├── erp_write_agent.py      # Entity-aware multi-turn write agent
│   ├── schema_inspector.py     # INFORMATION_SCHEMA column metadata
│   └── entities.py             # ERP business entity definitions
├── sql/
│   ├── validator.py            # Read SQL validator
│   ├── write_models.py         # InsertAction / UpdateAction Pydantic models
│   ├── write_validator.py      # Write action validator + table whitelist
│   └── write_sql_builder.py    # Parameterized SQL builder
├── schema/
│   └── indexer.py              # FAISS index builder
├── auth/
│   ├── auth.py                 # JWT logic
│   ├── models.py               # User model
│   └── router.py               # /auth/* routes
├── intent/
│   └── classifier.py           # READ vs WRITE intent detection
├── frontend/
│   ├── vite.config.js          # Vite dev proxy (all /api paths → :8000)
│   └── src/
│       ├── App.jsx             # Shell, tabs, auth routing
│       ├── pages/
│       │   ├── Askpage.jsx     # Natural-language query UI
│       │   ├── DataEntryPage.jsx  # Table selector, dynamic form, preview modal
│       │   ├── TablesPage.jsx  # Schema index browser
│       │   ├── HealthPage.jsx
│       │   └── RebuildPage.jsx
│       └── services/
│           └── api.js          # Axios client + all endpoint functions
├── test/
│   ├── check_env.py            # .env diagnostic
│   ├── db_test.py              # DB connectivity
│   ├── write_pipeline_test.py  # NLP write pipeline smoke test
│   └── data_entry_test.py      # Metadata + records pipeline smoke test
├── .env.example
├── requirement.txt
└── README.md
```

---

# Setup

### 1. Clone and configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
DB_SERVER=YOUR_SERVER
DB_NAME=YOUR_DATABASE
DB_USER=YOUR_USER
DB_PASSWORD=YOUR_PASSWORD
GROQ_API_KEY=YOUR_GROQ_API_KEY
```

### 2. Install Python dependencies

```bash
pip install -r requirement.txt
```

### 3. Build the FAISS schema index

```bash
python build_index.py
```

### 4. Seed an admin user

```bash
python seedadmin.py
```

### 5. Start the backend

```bash
uvicorn api.app:app --reload --port 8000
```

### 6. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and log in.

---

# Testing

```bash
# Check .env is loaded correctly
python test/check_env.py

# Test DB connectivity
python test/db_test.py

# Test NLP write pipeline (no DB writes)
python test/write_pipeline_test.py

# Test metadata + data entry pipeline (no DB writes)
python test/data_entry_test.py
```

---

# Security Notes

- Write execution (`/records/execute`) requires admin JWT — regular users can only preview.
- All writes use SQLAlchemy parameterized queries — no string concatenation of user values.
- System tables (`sys*`, `INFORMATION_SCHEMA`, etc.) are blocked from metadata and write endpoints.
- Identity and computed columns are locked read-only in the form and rejected server-side if submitted.
- The read pipeline blocks all DDL and DML keywords to prevent SQL injection through natural language.
