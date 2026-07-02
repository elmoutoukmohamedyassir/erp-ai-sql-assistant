# 🚀 ERP AI SQL Assistant

> **An AI-powered ERP platform built on top of Sage 100 SQL Server, combining natural language querying, secure data management, and a modern business interface.**

---

## 📖 Overview

ERP AI SQL Assistant is a full-stack web application that modernizes the interaction with a Sage 100 ERP database.

The platform provides two complementary experiences:

* **Administrators** can safely explore and manage ERP data using AI-powered querying and a secure data entry module.
* **Business users** interact with a simplified CRM interface without ever seeing database tables or SQL.

The project combines deterministic backend logic with AI capabilities while keeping database operations secure and fully validated.

---

# ✨ Features

## 🤖 AI SQL Assistant

Ask questions in natural language instead of writing SQL.

Example:

> Show me the top 10 customers by revenue.

The assistant automatically:

* Understands the question
* Retrieves relevant database schema
* Generates SQL using an LLM
* Validates generated SQL
* Executes safe SELECT queries
* Displays results in a modern table

### AI Pipeline

```text
Natural Language
        │
        ▼
Schema Retrieval
        │
        ▼
LLM SQL Generation
        │
        ▼
SQL Validation
        │
        ▼
SQL Execution
        │
        ▼
Results
```

---

## 📝 Admin Data Entry

A secure administration module allowing administrators to insert or update Sage ERP records without manually writing SQL.

Features:

* Dynamic table discovery
* Automatic schema inspection
* Dynamic forms
* Required field validation
* SQL preview
* Parameterized SQL generation
* Transaction execution
* SQL injection protection

Unlike the AI assistant, this module performs deterministic writes only.

---

## 👥 CRM Module *(Work in Progress)*

A business-oriented interface designed for non-technical users.

Instead of interacting with database tables, users manage business entities such as:

* Clients
* Orders *(planned)*
* Products *(planned)*
* Stock *(planned)*

The CRM communicates with the backend using business objects while the backend handles the mapping to Sage ERP tables.

---

## 🔐 Authentication & Authorization

The application uses JWT authentication.

Current roles:

* **Admin**

  * AI Assistant
  * Data Entry
  * CRM
  * Administration

* **User**

  * CRM access only

---

# 🏗 Architecture

```text
                     React + Vite Frontend
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
          ▼                                       ▼
   AI SQL Assistant                       CRM / Admin UI
          │                                       │
          └───────────────────┬───────────────────┘
                              ▼
                     FastAPI Backend
                              │
      ┌───────────────────────┼────────────────────────┐
      │                       │                        │
      ▼                       ▼                        ▼
 AI Query Engine      Admin Data Entry         CRM Services
      │                       │                        │
      └───────────────────────┴────────────────────────┘
                              │
                     SQLAlchemy + PyODBC
                              │
                       Microsoft SQL Server
                              │
                         Sage 100 Database
```

---

# 📂 Project Structure

```text
ERP-AI-SQL-Assistant/

├── backend/
│
├── api/
│   ├── app.py
│   ├── records.py
│   └── crm/
│
├── auth/
│   ├── auth.py
│   └── jwt.py
│
├── core/
│   ├── agent.py
│   ├── db.py
│   ├── prompts.py
│   └── validators.py
│
├── erp/
│   ├── schema_inspector.py
│   ├── erp_write_agent.py
│   └── metadata.py
│
├── frontend/
│   ├── src/
│   ├── pages/
│   ├── components/
│   ├── hooks/
│   └── services/
│
├── requirements.txt
├── package.json
└── README.md
```

---

# ⚙ Technology Stack

## Backend

* Python
* FastAPI
* SQLAlchemy
* PyODBC
* Microsoft SQL Server
* Pydantic
* JWT Authentication

---

## Frontend

* React
* Vite
* JavaScript
* Axios
* React Router

---

## Database

* Microsoft SQL Server
* Sage 100 ERP

---

## AI

* Large Language Models
* Prompt Engineering
* Retrieval-Augmented Generation (RAG)
* Schema-aware SQL generation

---

# 🔄 AI Query Flow

```text
User Question

↓

Retrieve Database Schema

↓

Generate SQL

↓

Validate SQL

↓

Execute Query

↓

Return Results
```

---

# 🔄 Data Entry Flow

```text
User Form

↓

Validate Table

↓

Validate Columns

↓

Validate Required Fields

↓

Generate Parameterized SQL

↓

Preview

↓

Confirm

↓

Execute Transaction

↓

SQL Server
```

---

# 🔒 Security

Security is a core design principle of the project.

Implemented protections include:

* JWT Authentication
* Role-Based Authorization
* Read-only AI SQL execution
* Table whitelist
* Column whitelist
* Schema validation
* Required field validation
* Parameterized SQL
* SQL Injection prevention
* Transaction management
* Server-side validation before execution

---

# 📡 REST API

## Authentication

```
POST /login
POST /register
```

---

## AI

```
POST /ask
```

---

## Metadata

```
GET /health
GET /tables
GET /tables/{table}/metadata
GET /rebuild
```

---

## Admin Data Entry

```
POST /records/create
POST /records/update
POST /records/execute
```

---

## CRM *(In Progress)*

```
GET /crm/clients
POST /crm/clients
PUT /crm/clients/{id}
DELETE /crm/clients/{id}
```

---

# 💻 Installation

## Clone the repository

```bash
git clone https://github.com/yourusername/erp-ai-sql-assistant.git

cd erp-ai-sql-assistant
```

---

## Backend

Create a virtual environment

```bash
python -m venv venv
```

Activate it

### Windows

```bash
venv\Scripts\activate
```

### Linux/macOS

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run FastAPI

```bash
uvicorn api.app:app --reload
```

---

## Frontend

```bash
cd frontend

npm install

npm run dev
```

---

# ⚙ Environment Variables

Example `.env`

```env
DB_SERVER=localhost
DB_NAME=BIJOU
DB_USER=sa
DB_PASSWORD=your_password

JWT_SECRET=your_secret

OPENAI_API_KEY=your_api_key
```

---

# 📸 Screenshots

Future screenshots can include:

* Login Page
* Dashboard
* AI Assistant
* SQL Results
* Admin Data Entry
* CRM Clients
* CRM Orders
* Stock Management

---

# 🛣 Roadmap

## ✅ Completed

* AI SQL Assistant
* SQL Validation
* Schema Retrieval
* JWT Authentication
* Dynamic Data Entry
* SQL Preview
* SQL Server Integration
* Sage Integration

---

## 🚧 In Progress

* CRM Clients

---

## 🔜 Planned

* Orders Management
* Products Management
* Stock Management
* Dashboard
* Reports
* Analytics
* AI Write Assistant
* Business Workflow Automation

---

# 🎯 Project Goals

The objective of this project is to modernize ERP systems by combining deterministic backend logic with Artificial Intelligence.

The platform aims to:

* Simplify ERP interactions
* Reduce SQL knowledge requirements
* Improve productivity
* Secure database operations
* Provide a modern user experience
* Enable future AI-powered business workflows

---

# 🤝 Contributing

Contributions are welcome.

To contribute:

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Push the branch.
5. Open a Pull Request.

---

# 📄 License

This project is intended for educational and professional purposes.

Ensure compliance with your organization's Sage ERP licensing, security policies, and database access rules before deploying in production.

---

# 👨‍💻 Author

**EL-MOUTOUK MOHAMED YASSIR**

AI/Data Engineer passionate about Artificial Intelligence, Data Engineering, Machine Learning, and Backend Development.

This project demonstrates the integration of AI technologies with enterprise ERP systems to build intelligent, secure, and user-friendly business applications.
