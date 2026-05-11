# 🌐 GeoLite2 IP Geolocation API

> Self-hosted · Offline lookups · User dashboard · Per-token rate control
> Built with [FastAPI](https://fastapi.tiangolo.com) + [MaxMind GeoLite2](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data)

---

## 📁 Project Structure

```
geoip_app/
├── app/
│   ├── auth.py            # Password hashing + JWT sessions
│   ├── config.py          # Settings loaded from .env
│   ├── database.py        # SQLite / SQLAlchemy setup
│   ├── dependencies.py    # Auth + per-token rate limiter
│   ├── geoip.py           # Core lookup engine
│   ├── main.py            # FastAPI app factory
│   ├── models.py          # User, ApiToken, UsageLog ORM models
│   ├── schemas.py         # Pydantic request/response models
│   ├── routers/
│   │   ├── dashboard.py   # Dashboard routes (auth, tokens, plan, usage)
│   │   ├── geo.py         # /geo/* endpoints
│   │   └── health.py      # /health endpoint
│   └── templates/         # Jinja2 HTML templates (Tailwind CSS)
│       ├── base.html
│       ├── login.html
│       ├── register.html
│       ├── dashboard.html
│       ├── tokens.html
│       ├── usage.html
│       ├── plan.html
│       └── settings.html
├── tests/
├── run.py
├── requirements.txt
├── .env.example
└── GeoLite2-City.mmdb     # MaxMind database (you must provide this)
```

---

## 🖥️ Running Locally

### Prerequisites

- Python 3.10+
- A MaxMind GeoLite2-City database file (`.mmdb`)

---

### Step 1 — Clone the repo

```bash
git clone https://github.com/yourname/geoip_app.git
cd geoip_app
```

---

### Step 2 — Create a virtual environment

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (CMD):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

---

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

---

### Step 4 — Get the GeoLite2 database

You need a free MaxMind account to download the database.

1. Sign up at [maxmind.com/en/geolite2/signup](https://www.maxmind.com/en/geolite2/signup)
2. Go to **Account → My License Key → Generate new license key**
3. Download **GeoLite2-City** (`.tar.gz` format)
4. Extract and place `GeoLite2-City.mmdb` in the project root (same folder as `run.py`)

```
geoip_app/
├── GeoLite2-City.mmdb   ← here
├── run.py
└── ...
```

---

### Step 5 — Configure environment

Copy the example file and edit it:

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```env
# Path to the .mmdb file (default works if it's in the project root)
GEOIP_DB_PATH=GeoLite2-City.mmdb

# Server
API_HOST=0.0.0.0
API_PORT=8089

# IMPORTANT: change this before going to production
SECRET_KEY=change-me-to-a-long-random-string

# Leave blank to use per-user tokens from the dashboard
API_KEY=

APP_ENV=development
```

> **Tip:** Generate a strong `SECRET_KEY` with:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

---

### Step 6 — Start the server

```bash
python run.py
```

The server starts at **http://localhost:8089**.

---

### Step 7 — Open the dashboard

Visit **http://localhost:8089/dashboard** in your browser.

You'll be redirected to the login page. Click **Create one** to register your first account.

---

## 🗂️ Dashboard Pages

| Page | URL | What it does |
|------|-----|-------------|
| Login | `/dashboard/login` | Sign in to your account |
| Register | `/dashboard/register` | Create an account, pick a plan |
| Overview | `/dashboard` | Stats, quota bar, 7-day chart, recent activity |
| API Tokens | `/dashboard/tokens` | Create / revoke / delete tokens, set per-token rate limits |
| Usage | `/dashboard/usage` | Full analytics — daily chart, endpoint breakdown, request log |
| Plan | `/dashboard/plan` | View plan details, upgrade or downgrade |
| Settings | `/dashboard/settings` | Change password, view API usage examples |

---

## 📦 Plans

| | Free | Pro | Enterprise |
|---|---|---|---|
| Rate limit | 10 req/min | 60 req/min | 300 req/min |
| Batch size | 10 IPs | 50 IPs | 100 IPs |
| Monthly quota | 1,000 | 50,000 | 500,000 |
| API tokens | 2 | 10 | 50 |
| Custom rate limits | ✗ | ✓ | ✓ |

Plans are managed in `app/models.py` → `PLANS` dict. Edit them freely — no payment integration is included by default.

---

## 🔑 Using the API

After registering, go to **API Tokens** and copy your token. Use it in the `X-API-Key` header:

### Single IP lookup

```bash
curl http://localhost:8089/geo/8.8.8.8 \
  -H "X-API-Key: gip_your_token_here"
```

```json
{
  "ip": "8.8.8.8",
  "country": "United States",
  "country_code": "US",
  "city": "Ashburn",
  "latitude": 37.751,
  "longitude": -97.822,
  "timezone": "America/Chicago"
}
```

### Batch lookup (up to 100 IPs)

```bash
curl -X POST http://localhost:8089/geo/batch \
  -H "X-API-Key: gip_your_token_here" \
  -H "Content-Type: application/json" \
  -d '{"targets": ["8.8.8.8", "1.1.1.1", "github.com"]}'
```

### Detect your own IP

```bash
curl http://localhost:8089/geo/me \
  -H "X-API-Key: gip_your_token_here"
```

### Health check (no auth needed)

```bash
curl http://localhost:8089/health
```

---

## ⚡ Per-Token Rate Limiting

Each token inherits the rate limit from its owner's plan. You can lower it per-token from the **API Tokens** page using the slider — useful for giving restricted access to third parties without changing your plan.

The rate limit is enforced per token value, not per IP.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 🗄️ Database

The app uses **SQLite** by default — no setup needed. The file `geoip_userstest.db` is created automatically in the project root on first run.

To use PostgreSQL instead, set `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/geoip
```

Then install the driver:

```bash
pip install psycopg2-binary
```

---

## 🔧 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEOIP_DB_PATH` | `GeoLite2-City.mmdb` | Path to the MaxMind `.mmdb` file |
| `API_HOST` | `0.0.0.0` | Bind host |
| `API_PORT` | `8089` | Bind port |
| `RATE_LIMIT` | `60` | Fallback rate limit (req/min) when no DB token is used |
| `API_KEY` | *(blank)* | Legacy single key — leave blank to use per-user tokens |
| `APP_ENV` | `development` | Set to `production` to lock down CORS |
| `SECRET_KEY` | *(insecure default)* | JWT signing key — **change this** |
| `DATABASE_URL` | `sqlite:///./geoip_userstest.db` | SQLAlchemy database URL |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Dashboard session duration |

---

## 🆘 Troubleshooting

**`ModuleNotFoundError`** — make sure your venv is activated and you ran `pip install -r requirements.txt`.

**`Database not found: GeoLite2-City.mmdb`** — the `.mmdb` file is missing. See Step 4.

**`401 Unauthorized` on API calls** — you need to pass `X-API-Key: <your-token>` in the header. Get a token from the dashboard.

**Dashboard shows 401** — your session cookie expired. Log in again at `/dashboard/login`.

**Port already in use** — change `API_PORT` in `.env` or kill the process using the port.

---

## 📄 License

GeoLite2 data is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) by MaxMind.
Project code is MIT licensed.
