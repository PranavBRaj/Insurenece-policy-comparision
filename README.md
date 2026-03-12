# PolicyLens — Insurance Policy Comparator

An AI-powered full-stack web application that lets users upload two insurance 
policy documents (.txt) and instantly receive a comprehensive, structured 
side-by-side comparison of coverage, exclusions, and premiums.

---

## Features

| Feature | Description |
|---|---|
| **AI Text Extraction** | Groq LLaMA-3.3-70B extracts structured coverage, exclusions, and premium data from raw policy text |
| **Side-by-Side Comparison** | Shared items, Policy 1-only items, and Policy 2-only items across coverage and exclusions sections |
| **Premium Breakdown** | Annual/monthly premiums, deductibles, copays, coinsurance, and out-of-pocket maximums compared |
| **Interactive Charts** | Coverage grouped bar, coverage donut, exclusions donut, premium bar, and similarity histogram (Chart.js) |
| **Anomaly Detection** | Rule-based + LLM hybrid scan against industry benchmarks (deductibles, OOP caps, missing coverages, high-risk exclusions) |
| **Policy Q&A Chatbot** | Ask any natural language question about the comparison and get an AI-sourced answer with confidence rating |
| **Personalised Recommendations** | Input your age, budget, health concerns, and risk tolerance to receive a tailored policy recommendation for 4 demographic profiles |
| **Plain-English Summary** | Jargon-free, Grade 6 reading level summary of both policies with strengths, weaknesses, and a head-to-head verdict |
| **PDF Export** | Download a formatted multi-section PDF comparison report via ReportLab |
| **Comparison History** | All comparisons persisted in MySQL and accessible from a dedicated History page |
| **Health Check** | `/health` endpoint reports server and database status |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11 · FastAPI · SQLAlchemy 2 · PyMySQL |
| **AI Engine** | Groq API · LLaMA-3.3-70B-Versatile |
| **Frontend** | React 18 · Vite 5 · React Router 6 · Chart.js |
| **Database** | MySQL 8 |
| **PDF Generation** | ReportLab |
| **Auth / Config** | Pydantic Settings · python-dotenv |

---

## Project Structure

```
Genai_2/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry-point, CORS, startup
│   │   ├── config.py                  # Settings from .env via pydantic-settings
│   │   ├── database.py                # SQLAlchemy engine + session factory
│   │   ├── models/
│   │   │   ├── db_models.py           # ORM: Policy, Comparison, UploadSession
│   │   │   └── schemas.py             # Pydantic request/response schemas
│   │   ├── routes/
│   │   │   ├── upload.py              # POST /api/upload-compare
│   │   │   └── comparison.py          # GET/DELETE comparisons, Q&A, export, etc.
│   │   └── services/
│   │       ├── text_parser.py         # Groq-powered .txt policy extraction
│   │       ├── comparison_engine.py   # Groq-powered side-by-side comparison
│   │       ├── qa_engine.py           # Natural language Q&A over comparison data
│   │       ├── recommendation_engine.py # Personalised policy recommendations
│   │       ├── anomaly_engine.py      # Rule + LLM anomaly detection
│   │       ├── plain_summary_engine.py # Plain-English consumer summaries
│   │       ├── visualisation_engine.py # Chart-ready data (no external API calls)
│   │       └── pdf_exporter.py        # ReportLab PDF report generation
│   ├── uploads/                       # Uploaded files (auto-created at runtime)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx                    # Router + header (PolicyLens brand)
│   │   ├── pages/
│   │   │   ├── HomePage.jsx           # Upload form + feature highlights
│   │   │   ├── ComparisonPage.jsx     # Full results page (all sections)
│   │   │   └── HistoryPage.jsx        # Past comparisons table
│   │   ├── components/
│   │   │   ├── ComparisonView.jsx     # Tabbed Coverage / Exclusions / Premiums
│   │   │   ├── SummaryBanner.jsx      # High-level statistics banner
│   │   │   ├── PolicyCharts.jsx       # Chart.js visualisations
│   │   │   ├── PolicyQA.jsx           # Chat-style Q&A interface
│   │   │   ├── PolicyRecommendation.jsx # Profile-based recommendation form
│   │   │   ├── PolicyAnomalies.jsx    # Anomaly detection panel
│   │   │   └── PolicyPlainSummary.jsx # Plain-English summary panel
│   │   └── services/
│   │       └── api.js                 # Axios API client
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
├── database/
│   └── schema.sql                     # MySQL schema initialisation script
├── sample_policies/                   # Sample .txt policy files for testing
└── README.md
```

---

## Prerequisites

- **Python 3.11+** — [python.org](https://www.python.org/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **MySQL 8** — running locally or remotely
- **Groq API Key** — [console.groq.com](https://console.groq.com)

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

# Copy the example env file and fill in your credentials
copy .env.example .env      # Windows
# cp .env.example .env       # macOS/Linux

# Edit .env – set at minimum:
#   DATABASE_URL=mysql+pymysql://root:<password>@localhost/your_db
#   SECRET_KEY=<any-long-random-string>
#   GROQ_API_KEY=<your-groq-api-key>

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

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload-compare` | Upload two `.txt` policy files; parse + compare |
| `GET` | `/api/comparisons` | List all comparisons (paginated) |
| `GET` | `/api/comparisons/{id}` | Get a specific comparison result |
| `DELETE` | `/api/comparisons/{id}` | Delete a comparison and its policies |
| `GET` | `/api/comparisons/{id}/visualisation` | Chart-ready visualisation data |
| `GET` | `/api/comparisons/{id}/export.pdf` | Download formatted PDF report |
| `POST` | `/api/comparisons/{id}/ask` | Ask a natural language question |
| `POST` | `/api/comparisons/{id}/recommendations` | Get personalised recommendations |
| `GET` | `/api/comparisons/{id}/anomalies` | Run anomaly detection scan |
| `GET` | `/api/comparisons/{id}/plain-summary` | Get plain-English summary |
| `GET` | `/api/history` | Upload session history |
| `GET` | `/health` | Health check (DB status) |

### POST `/api/upload-compare`

**Request:** `multipart/form-data` with fields:
- `policy1` – first `.txt` policy file (max 5 MB)
- `policy2` – second `.txt` policy file (max 5 MB)

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

## How It Works

### 1. Text Extraction (`text_parser.py`)
Plain-text `.txt` policy files are read and sent to the Groq LLaMA model, which extracts structured coverage items, exclusion items, and premium info as JSON.

### 2. Comparison Engine (`comparison_engine.py`)
Both parsed policies are sent together to Groq, which performs an intelligent side-by-side comparison — classifying items as shared or unique to each policy and computing similarity scores.

### 3. Downstream Analysis
All further features (anomaly detection, Q&A, recommendations, plain summary) use the stored comparison JSON as context for targeted Groq prompts — no re-parsing required.

### 4. Visualisation (`visualisation_engine.py`)
Chart datasets are derived purely from the comparison JSON — no additional API calls.

---

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string (MySQL) |
| `SECRET_KEY` | Internal signing key |
| `GROQ_API_KEY` | Your Groq API key |
| `GROQ_MODEL` | Groq model name (default: `llama-3.3-70b-versatile`) |
| `UPLOAD_DIR` | Directory for uploaded files (default: `uploads`) |
| `MAX_FILE_SIZE_MB` | Per-file upload size limit (default: `5`) |
| `CORS_ORIGINS` | Allowed CORS origins as JSON array |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Optional: path or JSON for Google Sheets export |
| `GOOGLE_SHEETS_SHARE_EMAIL` | Optional: email to share exported sheets with |

See `backend/.env.example` for a full template.

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

- **File format** – Only plain-text `.txt` files are accepted (max 5 MB per file).
- **Language** – English-language policies only.
- **Groq rate limits** – Free-tier Groq accounts have daily token quotas; large policy files may hit limits.
- **Token budget** – Policy text is truncated to ~28,000 characters (~7,000 tokens) for extraction to stay within the model's context window.