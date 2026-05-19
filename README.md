# ERP AI SQL Assistant

AI-powered Text-to-SQL assistant for Sage 100 / SQL Server databases.

Ask questions in natural language like:

- "Show all customers"
- "Top invoices this month"
- "List payment methods"
- "Show products with low stock"

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

## FastAPI REST API
Expose the assistant over HTTP for dashboards and frontend apps.

## SQL Injection & Dangerous Query Protection
Blocks:
- DROP
- DELETE
- UPDATE
- INSERT
- EXEC
- XP_*
- OPENROWSET
- and more

---

# Architecture

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