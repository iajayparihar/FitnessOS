# Feature List & Status

## Fitness Business OS

**Legend:** ⬜ Not Started · 🟨 In Progress · ✅ Shipped · 🧪 In Testing · ⏸️ Paused/Deferred

This file is the single source of truth for what's actually built vs. planned. Update it whenever a feature changes status — cross-reference with `ROADMAP.md` (phases/timing) and `CHANGELOG.md` (release history).

---

## Foundation
| Feature | Status | Notes |
|---|---|---|
| Project scaffolding (Docker, CI/CD) | 🟨 | `docker-compose` stack (Postgres + backend + frontend) done; CI/CD pending |
| Frontend testing console | ✅ | Vite+React+TS+MUI app to exercise auth/CRM/RBAC; Clerk or dev login |
| Authentication | ✅ | Clerk identity provider; JWT verification + JIT provisioning (see ADR-0006) |
| Email verification | ✅ | Handled by Clerk |
| Password reset | ✅ | Handled by Clerk |
| Standard error envelope + request-id | ✅ | Centralized handlers per `ERROR_HANDLING.md`; `X-Request-ID` on every response |
| Rate limiting | ✅ | Per-IP via `slowapi` |
| Logging & monitoring setup | 🟨 | Basic logging + request-id done; full observability (Sentry/metrics) pending |

## Multi-Tenant Platform
| Feature | Status | Notes |
|---|---|---|
| Tenant onboarding/signup | ✅ | `/auth/onboarding` (create org + owner) + `/auth/invites/accept` |
| Subscription/plan management | ⬜ | Phase 3 |
| Tenant branding/settings | 🟨 | Org create/list implemented; branding/settings endpoints pending |
| RBAC roles & permissions | ✅ | Roles, permissions, `require_permission`, audit trail |

## CRM
| Feature | Status | Notes |
|---|---|---|
| Lead capture (manual, walk-in) | ✅ | `POST /crm/leads`, list/get/update with filters + pagination |
| Trial management | ⬜ | Phase 4 (lead status supports `trial`; dedicated flow pending) |
| Follow-up / call & visit reminders | 🟨 | Follow-up create/list/complete done; automated reminders (Phase 13) pending |
| Lead sources tracking | ✅ | `GET/POST /crm/lead-sources` |
| Lead conversion tracking | ✅ | `POST /crm/leads/{id}/convert` |
| Lost-lead reason tracking | ✅ | `POST /crm/leads/{id}/lost` |
| CRM reports | ⬜ | Phase 4 / Phase 10 |

## Membership
| Feature | Status | Notes |
|---|---|---|
| Member registration | ⬜ | Phase 5 |
| Membership plans | ⬜ | Phase 5 |
| Renewals | ⬜ | Phase 5 |
| Freeze | ⬜ | Phase 5 |
| Transfer | ⬜ | Phase 5 |
| Cancellation | ⬜ | Phase 5 |
| Medical & emergency details | ⬜ | Phase 5 |
| Documents & digital agreement | ⬜ | Phase 5 |

## Attendance
| Feature | Status | Notes |
|---|---|---|
| QR code check-in | ⬜ | Phase 6 |
| Manual entry | ⬜ | Phase 6 |
| Attendance reports / peak hours | ⬜ | Phase 6 |
| Face recognition | ⬜ | Future |
| Biometric integration | ⬜ | Future |

## Billing
| Feature | Status | Notes |
|---|---|---|
| Invoices | ⬜ | Phase 7 |
| Payments | ⬜ | Phase 7 |
| Renewal billing | ⬜ | Phase 7 |
| Discounts & coupons | ⬜ | Phase 7 |
| Partial payments | ⬜ | Phase 7 |
| Refunds | ⬜ | Phase 7 |
| Payment gateway integration | ⬜ | Phase 7 |
| GST handling | ⬜ | Phase 7 |
| Receipts | ⬜ | Phase 7 |

## Trainer
| Feature | Status | Notes |
|---|---|---|
| Workout templates | ⬜ | Phase 8 |
| Exercise library | ⬜ | Phase 8 |
| Assign workouts | ⬜ | Phase 8 |
| Trainer notes | ⬜ | Phase 8 |
| Member progress tracking | ⬜ | Phase 8 |
| Trainer performance reports | ⬜ | Phase 8 |

## Nutrition
| Feature | Status | Notes |
|---|---|---|
| Meal plans | ⬜ | Phase 9 |
| Macro tracking (calories/protein/carbs/fat) | ⬜ | Phase 9 |
| Water intake tracking | ⬜ | Phase 9 |
| Body measurements | ⬜ | Phase 9 |
| Progress photos | ⬜ | Phase 9 |
| AI meal plans | ⬜ | Future (Phase 15) |

## Dashboard / Analytics
| Feature | Status | Notes |
|---|---|---|
| Revenue dashboard | ⬜ | Phase 10 |
| Membership/attendance analytics | ⬜ | Phase 10 |
| Lead pipeline view | ⬜ | Phase 10 |
| Collections & expense summary | ⬜ | Phase 10 |
| Growth/KPI dashboard | ⬜ | Phase 10 |

## Inventory
| Feature | Status | Notes |
|---|---|---|
| Equipment tracking | ⬜ | Phase 11 |
| Merchandise/supplement stock | ⬜ | Phase 11 |
| Purchases & suppliers | ⬜ | Phase 11 |
| Maintenance scheduling | ⬜ | Phase 11 |

## Expenses
| Feature | Status | Notes |
|---|---|---|
| Expense entry (rent, salary, etc.) | ⬜ | Phase 12 |
| Expense categories & reports | ⬜ | Phase 12 |

## Notifications
| Feature | Status | Notes |
|---|---|---|
| Email notifications | ⬜ | Phase 13 |
| SMS notifications | ⬜ | Phase 13 |
| WhatsApp notifications | ⬜ | Phase 13 |
| Push notifications | ⬜ | Phase 13 |
| Birthday wishes | ⬜ | Phase 13 |
| Payment/renewal reminders | ⬜ | Phase 13 |
| Missed-attendance nudges | ⬜ | Phase 13 |

## Mobile Apps
| Feature | Status | Notes |
|---|---|---|
| Member app | ⬜ | Phase 14 |
| Trainer app | ⬜ | Phase 14 |
| Owner app | ⬜ | Phase 14 |

## AI
| Feature | Status | Notes |
|---|---|---|
| Workout generator | ⬜ | Phase 15 |
| Diet generator | ⬜ | Phase 15 |
| Business insights | ⬜ | Phase 15 |
| Churn prediction | ⬜ | Phase 15 |
| Revenue forecasting | ⬜ | Phase 15 |
| AI chat assistant | ⬜ | Phase 15 |

## Marketplace
| Feature | Status | Notes |
|---|---|---|
| Trainer marketplace | ⬜ | Phase 16 |
| Nutrition marketplace | ⬜ | Phase 16 |
| Workout marketplace | ⬜ | Phase 16 |
| Supplement marketplace | ⬜ | Phase 16 |
| Equipment marketplace | ⬜ | Phase 16 |

## Enterprise
| Feature | Status | Notes |
|---|---|---|
| Multi-branch support | ⬜ | Phase 17 |
| Central dashboard | ⬜ | Phase 17 |
| White-label / custom branding | ⬜ | Phase 17 |
| Public APIs | ⬜ | Phase 17 |
| SSO | ⬜ | Phase 17 |
| Audit logs | ⬜ | Phase 17 |
| Dedicated support tier | ⬜ | Phase 17 |

---

*This document should be updated in the same PR that changes a feature's status — not batched later.*
