# Roadmap

## Fitness Business OS

This roadmap is phased deliberately: **foundation and core revenue/retention workflows before AI, marketplace, or enterprise features.** Do not jump ahead of the current phase without a documented reason (see `CLAUDE.md`).

Live build status per feature: [`FEATURES.md`](./FEATURES.md). Release history: [`CHANGELOG.md`](./CHANGELOG.md).

---

## Phase 0 — Research
- Competitor analysis (existing gym management software)
- Customer interviews (gym owners, studio owners)
- Product discovery & problem validation
- Wireframes
- Business model validation

## Phase 1 — Documentation
- PRD, Architecture, Database, API standards
- Coding standards, Security, Tenancy design
- Roadmap & feature specifications
*(This phase produces the documents in this `docs/` folder.)*

## Phase 2 — Project Foundation
- Authentication (JWT, refresh tokens, email verification, password reset)
- Docker & Docker Compose setup
- CI/CD pipeline (GitHub Actions)
- Logging, monitoring, configuration baseline

## Phase 3 — Multi-Tenant Platform
- Tenant/organization management
- Subscriptions & plans
- Tenant isolation (RLS + ORM enforcement)
- Roles & permissions (RBAC)

## Phase 4 — CRM
- Leads, walk-ins, trials
- Follow-ups, call/visit reminders
- Lead sources, conversion tracking, loss reasons, reports

## Phase 5 — Membership
- Member registration, plans, renewals
- Freeze, transfer, cancellation
- Medical details, emergency contacts, documents, digital agreements

## Phase 6 — Attendance
- QR code check-in, manual entry
- Attendance reports, peak-hour analytics
- *(Future: face recognition, biometric integration)*

## Phase 7 — Billing
- Invoices, payments, renewals
- Discounts, coupons, partial payments, refunds
- Payment gateway integration, GST, receipts

## Phase 8 — Trainer Module
- Workout templates, exercise library
- Workout assignment, trainer notes
- Member progress tracking, trainer performance reports

## Phase 9 — Nutrition Module
- Meal plans, macro tracking (calories/protein/carbs/fat)
- Water intake, body measurements, progress photos

## Phase 10 — Dashboard
- Revenue, membership, attendance, renewal analytics
- Lead pipeline, collections, expenses, growth KPIs

## Phase 11 — Inventory
- Equipment, merchandise/supplement stock
- Purchases, suppliers, maintenance

## Phase 12 — Expenses
- Expense entry & categorization (rent, salary, electricity, marketing, maintenance, misc.)

## Phase 13 — Notifications
- Email, SMS, WhatsApp, push
- Birthday wishes, payment/renewal reminders, missed-attendance nudges, offers

## Phase 14 — Mobile Apps
- Member app, Trainer app, Owner app

## Phase 15 — AI
- Workout generator, diet generator
- Business insights, churn prediction, revenue forecasting
- AI chat assistant

## Phase 16 — Marketplace
- Trainer, nutrition, workout, supplement, equipment marketplaces

## Phase 17 — Enterprise Features
- Multi-branch, central dashboard
- Custom branding, white-label
- Public APIs, SSO, audit logs, dedicated support

---

## Guiding Rule for Sequencing

Phases 4–7 (CRM → Membership → Attendance → Billing) represent the core revenue loop and should be treated as the MVP. **Nothing in Phases 13–17 should be started before Phases 2–7 are production-stable**, unless a specific customer/business reason is documented as an ADR in `DECISIONS.md`.

## Status Tracking

This document defines *what* and *in what order*. It intentionally does not commit to hard dates — timing depends on team size and velocity, to be layered in separately (e.g., a quarterly planning doc) once the team is staffed. Use `FEATURES.md` for granular, current status.
