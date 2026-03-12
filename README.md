# Insurance Policy Comparator

A full-stack web application that compares two insurance policy PDF documents side-by-side, highlighting coverage, exclusions, and premium differences.

---

## Tech Stack

| Layer    | Technology                            |
|----------|---------------------------------------|
| Backend  | Python 3.11+ · FastAPI · SQLAlchemy   |
| Frontend | React 18 · Vite 5 · React Router 6   |
| Database | MySQL 8                               |
| PDF      | pdfplumber · pypdf                    |

---

## Project Structure

```
Genai_2/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI application entry-point
│   │   ├── config.py             # Settings (reads .env)
│   │   ├── database.py           # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── db_models.py      # ORM models (Policy, Comparison, UploadSession)
│   │   │   └── schemas.py        # Pydantic request/response schemas
│   │   ├── routes/
│   │   │   ├── upload.py         # POST /api/upload-compare
│   │   │   └── comparison.py     # GET/DELETE /api/comparisons, GET /api/history
│   │   └── services/
│   │       ├── pdf_parser.py     # PDF text extraction & structured parsing
│   │       └── comparison_engine.py  # Policy diff / matching logic
│   ├── uploads/                  # Uploaded PDFs (created at runtime)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx               # Router + header
│   │   ├── index.css             # Global design tokens & utilities
│   │   ├── pages/
│   │   │   ├── HomePage.jsx      # Upload form
│   │   │   ├── ComparisonPage.jsx  # Results view
│   │   │   └── HistoryPage.jsx   # Past comparisons
│   │   ├── components/
│   │   │   ├── FileUploader.jsx  # Drag-and-drop PDF upload UI
│   │   │   ├── ComparisonView.jsx
│   │   │   ├── CoverageSection.jsx
│   │   │   ├── ExclusionsSection.jsx
│   │   │   ├── PremiumSection.jsx
│   │   │   ├── SectionTable.jsx  # Reusable shared/unique diff table
│   │   │   └── SummaryBanner.jsx # High-level statistics
│   │   └── services/
│   │       └── api.js            # Axios API client
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
├── database/
│   └── schema.sql                # Manual DB initialisation script
└── README.md
```

---

## Prerequisites

- **Python 3.11+** — [python.org](https://www.python.org/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **MySQL 8** — running locally or remotely

---

## Setup & Running

### 1. Database

```bash
# Log in to MySQL and run the schema
mysql -u root -p < database/schema.sql
```

This creates the `insurance_compare` database and all required tables.

---

### 2. Backend

```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy the example env file and fill in your MySQL credentials
copy .env.example .env      # Windows
# cp .env.example .env       # macOS/Linux

# Edit .env – set at minimum:
#   DATABASE_URL=mysql+pymysql://root:<password>@localhost:3306/insurance_compare
#   SECRET_KEY=<any-long-random-string>

# Start the API server (hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at **http://localhost:8000**  
Interactive docs: **http://localhost:8000/docs**

---

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server (proxies /api calls to port 8000)
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## API Reference

| Method | Endpoint                         | Description                                   |
|--------|----------------------------------|-----------------------------------------------|
| POST   | `/api/upload-compare`            | Upload two PDFs, parse & compare them         |
| GET    | `/api/comparisons`               | List all comparisons (paginated)              |
| GET    | `/api/comparisons/{id}`          | Get a specific comparison result              |
| DELETE | `/api/comparisons/{id}`          | Delete a comparison and its policies          |
| GET    | `/api/history`                   | Upload session history                        |
| GET    | `/health`                        | Health check (includes DB connectivity)       |

### POST `/api/upload-compare`

**Request:** `multipart/form-data` with fields:
- `policy1` – first PDF file
- `policy2` – second PDF file

**Response:**
```json
{
  "session_id": "abc123",
  "policy1":     { "id": 1, "filename": "...", "parse_status": "completed", ... },
  "policy2":     { "id": 2, "filename": "...", "parse_status": "completed", ... },
  "comparison": {
    "id": 1,
    "status": "completed",
    "comparison_result": {
      "coverage":   { "common": [...], "only_in_policy1": [...], "only_in_policy2": [...] },
      "exclusions": { "common": [...], "only_in_policy1": [...], "only_in_policy2": [...] },
      "premiums": {
        "policy1": { "annual_premium": "$1,200", "deductible": "$500", ... },
        "policy2": { "annual_premium": "$1,500", "deductible": "$1,000", ... },
        "differences": ["Annual Premium: Policy 1 = $1,200, Policy 2 = $1,500"]
      },
      "summary": {
        "shared_coverage_items": 8,
        "policy1_advantages": [...],
        "policy2_advantages": [...]
      }
    }
  }
}
```

---

## Comparison Logic

### PDF Parsing (`pdf_parser.py`)

1. **Text extraction** – primary: `pdfplumber` (preserves layout, handles tables); fallback: `pypdf`
2. **Section detection** – regex patterns match common insurance section headers (`Coverage`, `Exclusions`, `Premium`, etc.)
3. **Item extraction** – bullet/numbered list items are parsed first; lines with relevant keywords are used as fallback
4. **Amount extraction** – dollar values (`$x,xxx.xx`), percentages, deductibles, co-pays, and co-insurance are extracted via targeted regex

### Comparison Engine (`comparison_engine.py`)

- Items are compared using **`difflib.SequenceMatcher`** on normalised text (lower-case, punctuation stripped)
- A similarity threshold of **0.55** classifies items as "shared" vs "unique"
- Premiums are compared field-by-field and differences are listed as plain-text sentences

---

## Environment Variables (`.env`)

| Variable            | Default                                             | Description                             |
|---------------------|-----------------------------------------------------|-----------------------------------------|
| `DATABASE_URL`      | `mysql+pymysql://root:password@localhost:3306/...`  | SQLAlchemy connection string            |
| `SECRET_KEY`        | `change-me`                                         | Used for internal signing (extend as needed) |
| `UPLOAD_DIR`        | `uploads`                                           | Directory for uploaded PDFs             |
| `MAX_FILE_SIZE_MB`  | `20`                                                | Per-file upload size limit in MB        |
| `CORS_ORIGINS`      | `http://localhost:5173,http://127.0.0.1:5173`       | Allowed CORS origins (comma-separated)  |

---

## Building for Production

### Backend

Use a production ASGI server such as **Gunicorn** + **Uvicorn workers**:

```bash
pip install gunicorn
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
```

### Frontend

```bash
cd frontend
npm run build
# Output is in frontend/dist/ – serve with any static file server
```

---

## Notes & Limitations

- **Scanned/image PDFs** – PDFs containing only scanned images (no embedded text) cannot be parsed without OCR. The API returns a descriptive error in this case.
- **Non-standard layouts** – Policies with unusual formatting may have reduced extraction accuracy. The keyword-scan fallback provides basic results for these cases.
- **Language** – English-language policies only (regex patterns are English-specific).
