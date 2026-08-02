# Product Requirements Document (PRD)

## Fitness Business OS

**Status:** Draft — Living Document
**Owner:** Product
**Last Updated:** See `CHANGELOG.md`

---

## 1. Problem Statement

Fitness businesses (gyms, studios, functional training centers) run on a patchwork of tools: spreadsheets, WhatsApp, paper registers, and generic gym-check-in apps that only handle members and attendance. This causes:

- Lost leads due to no follow-up system
- Missed renewals and revenue leakage
- No visibility into business health (revenue, churn, retention)
- Manual, repetitive admin work for owners and staff
- Poor member experience (no self-service, no communication)
- No path to scale beyond one location

Existing "gym management software" solves only a slice of this (members, attendance, basic billing). None of them act as a full **business operating system**.

---

## 2. Product Vision

> Fitness Business OS is the Shopify for fitness businesses — a single platform that runs the entire business, from the first lead to a multi-branch franchise.

We are not competing on "check-in and billing." We are competing on **helping owners grow and run their business end to end.**

---

## 3. Target Users

### Primary
- Gym Owners
- Fitness Studio Owners
- Functional Training Center Owners
- CrossFit Box Owners

### Secondary
- Yoga Studio Owners
- Independent Personal Trainers
- Nutritionists / Dietitians
- Wellness Centers

### Future
- Gym Chains
- Franchises
- Enterprise Fitness Brands

### Roles Within a Tenant
Super Admin · Gym Owner · Manager · Receptionist · Trainer · Nutritionist · Member

---

## 4. Business Model

| Plan | Price | Target |
|---|---|---|
| Starter | ₹999/month | Single-location, small gyms |
| Growth | ₹1999/month | Growing studios, multi-staff |
| Enterprise | Custom | Multi-branch, franchises, white-label |

**Future revenue streams:** annual subscriptions, white-label licensing, AI add-ons, WhatsApp automation credits, SMS credits, setup fees, API access, marketplace commission.

---

## 5. Product Pillars (End-to-End Flow)

```
Lead Management → Membership → Billing → Attendance → Workout →
Nutrition → Retention → Marketing → Analytics → Growth
```

Traditional gym software stops at Members → Attendance → Payments. Fitness Business OS covers the entire funnel and lifecycle.

---

## 6. Core Modules (Scope Summary)

| Module | Key Capabilities |
|---|---|
| **CRM** | Leads, walk-ins, trials, follow-ups, call/visit reminders, lead sources, conversion tracking, loss reasons |
| **Membership** | Registration, plans, renewals, freeze, transfer, cancellation, medical/emergency info, documents, digital agreements |
| **Attendance** | QR check-in, manual entry, peak-hour reports; future: face recognition, biometrics |
| **Billing** | Invoices, payments, renewals, discounts, coupons, partial payments, refunds, payment gateway, GST, receipts |
| **Trainer** | Workout templates, exercise library, workout assignment, trainer notes, member progress, trainer performance |
| **Nutrition** | Meal plans, macros (calories/protein/carbs/fat), water intake, body measurements, progress photos; future: AI meal plans |
| **Inventory** | Equipment, supplements/merchandise, stock, purchases, suppliers, maintenance |
| **Expenses** | Rent, salary, electricity, marketing, maintenance, miscellaneous |
| **Dashboard** | Revenue, members, attendance, renewals, lead pipeline, collections, expenses, growth, KPIs |
| **Notifications** | Email, SMS, WhatsApp, push; birthday wishes, payment/renewal reminders, missed-attendance nudges, offers |
| **Mobile Apps** | Member app, Trainer app, Owner app |
| **AI** | Workout generator, diet generator, business insights, churn prediction, revenue forecasting, AI chat assistant |
| **Marketplace** | Trainer, nutrition, workout, supplement, equipment marketplaces |
| **Enterprise** | Multi-branch, central dashboard, custom branding, white-label, public APIs, SSO, audit logs, dedicated support |

Detailed, phase-by-phase scope: [`ROADMAP.md`](./ROADMAP.md). Current build status: [`FEATURES.md`](./FEATURES.md).

---

## 7. Design Principle — The Feature Filter

Every proposed feature must answer **yes** to at least one:

- Does it increase revenue?
- Does it improve member retention?
- Does it save time?
- Does it automate manual work?
- Does it improve business insights?
- Does it improve customer experience?

If the answer is "no" across the board, it does not belong in the MVP.

---

## 8. Non-Functional Requirements

Production-ready · Secure · Scalable · Maintainable · Well-documented · Testable · Modular · Cloud-native · API-first · Tenant-isolated.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) and [`SECURITY.md`](./SECURITY.md).

---

## 9. Success Metrics

### Business Metrics
- Monthly Recurring Revenue (MRR)
- Customer Lifetime Value (LTV)
- Customer Acquisition Cost (CAC)
- Churn rate
- Net Revenue Retention (NRR)

### Product Metrics
- Active gyms (tenants)
- Active members (end-users of tenants)
- Attendance volume
- Membership renewal rate
- Lead-to-member conversion rate
- Daily Active Users (DAU)

---

## 10. Out of Scope (For Now)

- Microservices architecture (explicitly deferred — see `DECISIONS.md`)
- Face recognition / biometric attendance (Phase 6+ future item)
- AI features (Phase 15 — after core modules are solid)
- Marketplace (Phase 16)
- Multi-branch / white-label (Phase 17)

---

## 11. Open Questions

- Final pricing/packaging per plan tier (feature gating across Starter/Growth/Enterprise)
- Payment gateway provider(s) for the Indian market vs. international expansion
- WhatsApp Business API provider selection
- Which markets to target first (India-only vs. broader)

These should be resolved during Phase 0 (Research) and tracked as ADRs once decided.
