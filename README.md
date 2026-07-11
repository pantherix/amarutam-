# Amrutam Telemedicine System Backend

A production-grade, highly scalable, reliable, and secure backend engine for Amrutam's Telemedicine System. Built with **Python 3.14 / FastAPI**, **PostgreSQL**, **Redis**, and **arq (async worker)**.

---

## Key Architecture & Security Features

- **Pessimistic Locking & Unique Constraints**: Prevents doctor double-bookings even under heavy concurrent loads.
- **Application-Level Envelope Encryption**: PHI (diagnosis, medications) and sensitive PII (name, phone) are encrypted using AES-256-GCM before writing to the database, ensuring HIPAA compliance.
- **Multi-Factor Authentication (MFA)**: Built-in TOTP verification (MFA step-up authentication) using `pyotp`.
- **API Idempotency Middleware**: Enforces idempotency via an `Idempotency-Key` header on write requests using a Redis cache, securing duplicate payments and bookings.
- **Asynchronous Background Processing**: Offloads heavy tasks (prescriptions PDF generation, email/SMS notifications) to `arq` worker threads.
- **Production Infrastructure (IaC)**: Includes modular Terraform configuration for AWS (VPC, Fargate, RDS, ElastiCache, ALB, KMS).
- **Observability Stack**: Prometheus metrics endpoint (`/metrics`) exposing request counters and latency histograms, combined with correlation ID injection via structured JSON logs.

---

## Directory Structure

```
├── .github/
│   └── workflows/
│       └── ci.yml             # CI/CD Pipeline (Build and Test)
├── docs/
│   ├── architecture.md        # Technical System Design & Diagrams
│   ├── security_threat_model.md # Threat Modeling (STRIDE) & Security Controls
│   └── openapi.json           # Extracted OpenAPI 3.0 Specs
├── infra/
│   ├── docker-compose.yml     # Local orchestration configuration
│   ├── prometheus.yml         # Prometheus scraper configuration
│   └── terraform/             # AWS Terraform Production IaC
├── src/
│   ├── app/
│   │   ├── api/               # FastAPI controllers & dependencies
│   │   ├── middleware/        # Idempotency, rate limiter, and metrics middlewares
│   │   ├── models/            # SQLAlchemy database entities
│   │   ├── repositories/      # Data access layer (with field encryption)
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Core business services (Auth, Booking, Payments)
│   │   ├── worker/            # Background worker task handlers
│   │   ├── config.py          # Configuration loading
│   │   ├── database.py        # Async engine pool
│   │   ├── security.py        # Cryptography, JWT, and MFA helpers
│   │   └── main.py            # API app entrypoint
│   └── tests/                 # Integration and concurrency test suite
├── Dockerfile                 # Multi-stage production container file
├── requirements.txt           # Dependency file
└── README.md                  # System overview & setup guides
```

---

## Local Setup & Execution

### Prerequisites
- Docker & Docker Desktop
- Python 3.14+ (if running on the host)

### Run using Docker Compose
Spin up the entire stack (FastAPI server, arq background worker, Postgres, Redis, Prometheus) with a single command:

```bash
docker compose -f infra/docker-compose.yml up --build -d
```

#### Exposing Endpoints:
- **FastAPI API Server**: `http://localhost:8005`
- **Interactive OpenAPI Documentation**: `http://localhost:8005/docs`
- **Prometheus Dashboard**: `http://localhost:9090`
- **Prometheus Scraped Metrics**: `http://localhost:8005/metrics`

---

## Verification & Testing

### Running Tests inside Virtual Environment
To create a clean virtual environment and run the test suite locally:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows Powershell)
.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt

# Run testing suite
pytest src/tests -v
```

### Running Tests inside Docker Container
To run the tests inside an isolated Docker container without local dependencies:

```bash
docker build -t amrutam-tests --target builder .
docker run --rm amrutam-tests pytest src/tests -v
```
