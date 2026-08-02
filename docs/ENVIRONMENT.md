# Environment Variables

## Fitness Business OS

All configuration is environment-driven — no hardcoded secrets or environment-specific values in code (see `SECURITY.md`, `CODING_STANDARDS.md`). Backend config is loaded via Pydantic `BaseSettings` from environment variables / `.env` files.

`.env` files are **never committed**. `.env.example` files (committed) document required keys with placeholder/dummy values.

---

## 1. Backend (`backend/.env`)

### App
| Variable | Description | Example |
|---|---|---|
| `APP_ENV` | Current environment | `local` \| `staging` \| `production` |
| `APP_DEBUG` | Debug mode toggle | `true` \| `false` |
| `APP_SECRET_KEY` | General app secret (session signing, etc.) | `<random 64+ char string>` |
| `APP_HOST` | Bind host | `0.0.0.0` |
| `APP_PORT` | Bind port | `8000` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins | `http://localhost:5173` |

### Database
| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Full Postgres connection string | `postgresql+asyncpg://user:pass@host:5432/fitness_os` |
| `DATABASE_POOL_SIZE` | Connection pool size | `10` |
| `DATABASE_MAX_OVERFLOW` | Pool overflow limit | `5` |

### Redis / Celery
| Variable | Description | Example |
|---|---|---|
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker (usually same as Redis) | `redis://localhost:6379/1` |
| `CELERY_RESULT_BACKEND` | Celery result backend | `redis://localhost:6379/2` |

### Auth / JWT
| Variable | Description | Example |
|---|---|---|
| `JWT_SECRET_KEY` | JWT signing secret (or private key if asymmetric) | `<random 64+ char string>` |
| `JWT_ALGORITHM` | Signing algorithm | `HS256` \| `RS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | `15` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | `30` |

### Email
| Variable | Description | Example |
|---|---|---|
| `EMAIL_PROVIDER` | Provider selection | `sendgrid` \| `ses` \| `postmark` |
| `EMAIL_API_KEY` | Provider API key | `<secret>` |
| `EMAIL_FROM_ADDRESS` | Default from address | `no-reply@fitnessbusinessos.com` |

### SMS / WhatsApp
| Variable | Description | Example |
|---|---|---|
| `SMS_PROVIDER` | Provider selection | `msg91` \| `twilio` |
| `SMS_API_KEY` | Provider API key | `<secret>` |
| `WHATSAPP_PROVIDER` | Provider selection | `interakt` \| `gupshup` \| `meta` |
| `WHATSAPP_API_KEY` | Provider API key | `<secret>` |

### Payment Gateway
| Variable | Description | Example |
|---|---|---|
| `PAYMENT_GATEWAY_PROVIDER` | Provider selection | `razorpay` \| `cashfree` \| `stripe` |
| `PAYMENT_GATEWAY_KEY_ID` | Public/key ID | `<value>` |
| `PAYMENT_GATEWAY_KEY_SECRET` | Secret key | `<secret>` |
| `PAYMENT_GATEWAY_WEBHOOK_SECRET` | Webhook signature verification secret | `<secret>` |

### Object Storage
| Variable | Description | Example |
|---|---|---|
| `STORAGE_PROVIDER` | Provider selection | `s3` \| `spaces` |
| `STORAGE_BUCKET_NAME` | Bucket name | `fitness-os-uploads` |
| `STORAGE_REGION` | Region | `ap-south-1` |
| `STORAGE_ACCESS_KEY_ID` | Access key | `<secret>` |
| `STORAGE_SECRET_ACCESS_KEY` | Secret key | `<secret>` |

### Observability
| Variable | Description | Example |
|---|---|---|
| `SENTRY_DSN` | Error tracking DSN | `<value>` |
| `LOG_LEVEL` | Logging verbosity | `INFO` \| `DEBUG` \| `WARNING` |

---

## 2. Frontend (`frontend/.env`)

| Variable | Description | Example |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:8000/api/v1` |
| `VITE_SENTRY_DSN` | Frontend error tracking DSN | `<value>` |
| `VITE_APP_ENV` | Current environment | `local` \| `staging` \| `production` |

Only variables prefixed `VITE_` are exposed to the browser bundle — never put secrets here (frontend env vars are public).

---

## 3. Environment Parity Rules

- `.env.example` in both `backend/` and `frontend/` must always be kept up to date whenever a new variable is introduced — this is part of the PR that adds the variable, not a follow-up.
- Local, staging, and production use the **same variable names**, only different values — never rename a variable per-environment.
- Production secrets are stored in the cloud provider's secrets manager (see `DEPLOYMENT.md`, `SECURITY.md`), injected at deploy/runtime — never stored as plain files on servers.

---

## 4. Adding a New Environment Variable — Checklist

1. Add it to the appropriate `.env.example` file with a placeholder value and a one-line comment.
2. Add it to this document (`ENVIRONMENT.md`) with description and example.
3. Load it via the typed `Settings`/config object — never `os.environ.get(...)` scattered through the codebase.
4. If it's a secret, confirm it's added to the staging/production secrets manager before merging code that depends on it.
