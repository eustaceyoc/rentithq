# Architecture

This describes the code that is in the repository. Planned pieces are labeled as planned.

## Shape

A modular monolith. One Django project and one PostgreSQL database. The React app is a separate Vite build. They share no business rules: permissions, occupancy overlap, and money parsing live on the server. The browser only displays results and form errors. Invoice totals and outstanding amounts are calculated on the server.

```text
browser
  -> Vite dev server :43123  (or nginx static files in production)
       -> proxy /api  ->  Django :43124  (or Gunicorn)
                              -> PostgreSQL
```

Production target, not scripted beyond the process model: one VPS, one hostname, nginx serving `frontend/dist` and proxying `/api/` and `/admin/` to Gunicorn. Kubernetes is out of scope. See ADR-011.

## Repository layout

```text
backend/config/          settings, urls, wsgi/asgi
backend/accounts/        email user model, session API, platform admin
backend/organizations/   workspaces, memberships, audit events, tenant resolver
backend/properties/      properties, buildings, floors, spaces, beds
backend/residents/       resident contact profiles
backend/bookings/        reservations
backend/tenancies/       agreements, stays, occupancy holds
backend/billing/         invoices, payments, allocations, receipts, arrears
backend/maintenance/     maintenance requests and status history
backend/reports/         occupancy, arrears, collections, and maintenance reports
backend/common/          health probes, error shape, pagination, money helpers
backend/config/storage.py  file-storage seam; backup credentials are not read
backend/tests/           pytest suite
frontend/src/            account, workspace, property, resident, stay, billing, maintenance, and report screens, plus the health client
docs/                    product, domain, API, security, setup
product-prompts/         phase prompts; do not rewrite them
```

`config.wsgi` and `config.asgi` default to `config.settings.production`, which refuses to boot without a strong secret, explicit hosts, and a PostgreSQL URL. `manage.py` defaults to `config.settings.local`.

## Request path

`/api/v1/` is included from `config.api_v1`. Implemented views:

- `GET /api/v1/health/` — process is up. No database query.
- `GET /api/v1/health/ready/` — `SELECT 1`. Failure is HTTP 503 and `{"status":"unavailable"}`.

Both set `Cache-Control: no-store`, allow anonymous access, and skip authentication so a probe does not create a session.

Session, workspace, and membership views use session authentication. Register, login, and the CSRF cookie endpoint allow anonymous callers. Login and registration enforce CSRF in the view because DRF skips that check until a session already exists.

- `GET /api/v1/auth/csrf/`, `POST /api/v1/auth/register/`, `POST /api/v1/auth/login/`, `POST /api/v1/auth/logout/`, `GET /api/v1/auth/session/`
- `GET` and `POST /api/v1/workspaces/`, plus `GET`, `PATCH`, and `DELETE /api/v1/workspaces/<id>/`
- `GET` and `POST /api/v1/memberships/`, plus `GET`, `PATCH`, and `DELETE /api/v1/memberships/<id>/`
- The same verbs for `/api/v1/properties/`, `/api/v1/buildings/`, `/api/v1/floors/`, `/api/v1/spaces/`, and `/api/v1/beds/`
- `GET` and `POST` for `/api/v1/residents/`, `/api/v1/bookings/`, `/api/v1/tenancies/`, and `/api/v1/assignments/`, plus the detail, cancel, convert, check-in, check-out, end, and transfer actions in `docs/API_CONTRACT.md`
- `GET /api/v1/availability/`
- `GET` and `POST /api/v1/invoices/`, `GET /api/v1/invoices/<id>/`, and `POST /api/v1/invoices/<id>/void/`
- `GET` and `POST /api/v1/payments/`, `GET /api/v1/payments/<id>/` (the receipt), `POST /api/v1/payments/<id>/void/`, and `POST /api/v1/payments/<id>/refunds/`
- `POST /api/v1/allocations/` and `POST /api/v1/allocations/<id>/reverse/`
- `GET /api/v1/arrears/?on=YYYY-MM-DD`
- `GET` and `POST /api/v1/maintenance-requests/`, plus `GET` and `PATCH /api/v1/maintenance-requests/<id>/`
- `GET /api/v1/reports/occupancy/`, `/api/v1/reports/arrears/`, `/api/v1/reports/collections/`, and `/api/v1/reports/maintenance/`

## Payments

Staff issue an invoice with lines, or copy a tenancy's agreed fee and optional deposit onto lines. They record a payment and allocate part or all of it to one or more invoices for the same resident. Outstanding amount and unallocated amount are derived. A void, allocation reversal, or refund is its own row. The payment detail is the receipt. Arrears are issued invoices that are due on or before the chosen date and still have an outstanding amount.

Manual methods are `cash`, `bank_transfer`, `mobile_money`, `card`, and `other`. Saving a card or mobile-money payment does not contact a gateway.

Paystack is the chosen gateway for resident mobile money and card payments (ADR-009). It is not integrated. Phase 02 adds that adapter and must use real credentials, verify webhook signatures, and treat provider events as idempotent. This build has no Paystack key, webhook, or HTTP client.

`billing.Payment` keeps `provider`, `provider_reference`, and `provider_status` nullable. A manual payment leaves them null. A later provider payment stores the provider name, that provider's reference, and the provider's status. Those fields are separate from `method` and from the payment status `recorded` or `void`. `pay_provider_reference_unique` is a partial unique constraint on workspace, provider, and provider reference where the reference is present. The write API rejects those three fields so a client cannot pretend a manual row came from Paystack.

The owner and finance write money. A property manager can read it. Maintenance cannot. A resident reads only their own invoices and payments. Money writes lock the workspace row and append an audit event. There is no `PATCH` or `DELETE` of a money row.

The browser formats money for display with the currency's minor units. GHS uses two decimal places. The API still returns four. `frontend/src/money.ts` rounds half away from zero. Inputs still send the four-place string the server stores.

## Maintenance and reports

A maintenance request names a property and, optionally, a space, a bed, and a resident. Each change appends `maintenance.MaintenanceUpdate`. The owner and property manager assign. Maintenance staff see assigned work and unassigned requests they filed. Finance can file and read, and cannot update. A resident files against their own profile. The request does not change space availability. `location_blocked` only reports an existing maintenance block. Attachment fields are rejected.

The home page keeps properties, stays, billing, and maintenance on one screen. Creating a property, room, bed, resident, or tenancy tells the other sections to load again, so a room just added can be selected for a stay or a request without a reload.

Reports call the same membership resolver and then the same read rules as the records they summarize. Arrears reuse `billing.services.list_arrears`. Occupancy reuse `tenancies.services.list_availability`. The maintenance report uses `maintenance.services.visible_request_rows`, so a maintenance login does not receive the workspace total. `export=csv` is the same queryset. There is no warehouse and no cached total.

`Workspace.plan_code` is returned on the workspace payload and ignored by feature checks. Platform admin edits it.

## Active workspace

Membership views call `organizations.access.resolve_active_membership` before they query:

1. Authenticate the session.
2. Load active memberships for that user.
3. Choose the workspace from `X-Workspace-Id` when it matches one of those memberships. One membership may omit the header. Several memberships require it.
4. Scope the membership query to that workspace. A resident's query is further limited to their own row.
5. Reject a write whose `workspace_id` is anything else.

Workspace URLs are authorized by membership in that workspace, not by the header. "My workspaces" and the session payload do not use the header and do not list other tenants. Property, resident, booking, tenancy, assignment, availability, invoice, payment, allocation, arrears, maintenance, and report views call the same resolver, then check the role. Residents are rejected before any property, availability, arrears, or report query. Their resident, tenancy, assignment, invoice, payment, and maintenance queries are limited to the profile linked to their user. A `workspace_id` query parameter is ignored. Do not trust a workspace id from a request body. Occupancy writes lock the spaces they touch and replace derived holds inside the same transaction. The exclusion constraints are the backstop.

## Settings modules

| Module | Use |
| --- | --- |
| `config.settings.base` | Shared settings. Requires `DATABASE_URL` and `DJANGO_SECRET_KEY`. Engine must be PostgreSQL. |
| `config.settings.local` | Development. Debug on by default. Console email. Browsable API enabled. |
| `config.settings.test` | pytest. Secure-cookie flags relaxed because the test client is HTTP. Locmem email. |
| `config.settings.production` | Debug forced off. Secure cookies, SSL redirect, health exempt from redirect. SMTP mailer declared but unused. |

Outbound email is not sent by this build. Local mail prints to the console. Tests use locmem. Production names the SMTP backend so `check --deploy` does not treat the process as a development mailer. `EMAIL_HOST` is empty until a later phase.

## Static and media

The web build is Vite's `frontend/dist`. Django `collectstatic` is only for admin assets. `STORAGES["default"]` comes from `config.storage.file_storage_config`. The default is the local filesystem. `FILE_STORAGE_BACKEND=s3` points at an S3-compatible private bucket using only environment values. Backup credentials are not part of that setting. There is no upload view. See ADR-012.

## Processes

- Development API: `manage.py runserver 127.0.0.1:43124`
- Development web: `npm run dev --prefix frontend` on port 43123
- Production API: `gunicorn config.wsgi:application` with production settings in the environment
- Production web: static files from `npm run build`

Gunicorn is a locked dependency. A production process was not deployed from this environment.
