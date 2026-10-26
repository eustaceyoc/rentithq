# Security

## Assets

Workspace operational data, property and room records, resident contact details, occupancy history, invoices, payments, staff accounts, and session cookies. This build stores accounts, workspaces, memberships, property records, resident profiles, bookings, tenancies, stays, invoices, payments, allocations, and the records that void, reverse, or refund them. It does not store a Paystack key or a provider charge. Resident profiles store a name and optional phone, email, and login link.

## Assumptions

The API is reachable from the public internet once deployed. Tenants are mutually untrusted. A signed-in user may belong to more than one workspace and must not see the others. Staff in one role must not gain another role by hiding a button. Platform administration requires `is_staff` and `is_superuser`. Workspace owners get neither.

No country privacy law is implemented or claimed. The owner still needs to decide what resident data is justified.

## What is enforced now

- PostgreSQL is required. SQLite is rejected at startup.
- Production refuses to start when the secret, hosts, or database URL is missing or weak, when debug is on, when hosts is `*`, or when a CSRF origin is not HTTPS.
- `DEBUG` comes from the environment and is forced off in production settings.
- Session cookies are `HttpOnly` and `SameSite=Lax`. They are `Secure` when debug is off. Tests relax the secure flag because the test client is plain HTTP.
- CSRF middleware is on. The CSRF cookie is not `HttpOnly`, so a future SPA can read it and send `X-CSRFToken`. That is deliberate.
- SSL redirect is on in production. `/api/v1/health/` is exempt so a local probe can use HTTP behind a TLS-terminating proxy. Set `DJANGO_SECURE_HSTS_SECONDS` only after HTTPS is confirmed. It defaults to 0, and `check --deploy` warns `security.W004` until then.
- Default DRF permission is authenticated. Health probes are the explicit anonymous exception.
- API 500s do not return exception text or settings. Readiness failures do not return the database error.
- Passwords are hashed. Validators run when users are created through the manager. The common password `password` is rejected.
- Secrets belong in the environment. `.env` is gitignored. `.env.example` has placeholders only.
- Logs do not record request bodies. Database readiness logs the exception class, not the driver message.

Row-level security is not configured. Do not describe it as on.

## Tenant isolation

ADR-005 is enforced for workspaces, memberships, property records, residents, bookings, tenancies, assignments, invoices, payments, maintenance requests, and reports. Tests in `backend/tests/test_workspaces.py`, `backend/tests/test_properties.py`, `backend/tests/test_occupancy.py`, `backend/tests/test_billing.py`, `backend/tests/test_maintenance.py`, and `backend/tests/test_reports.py` cover list, retrieve, update, delete, and attaching another workspace's id. Report tests also check that a second workspace's names and amounts are absent from JSON and CSV. A non-member receives 404 with a generic body. The other workspace's name is not in that body. Attaching a space, building, floor, bed, resident, or stay to a parent in another workspace returns 404 and creates no row. Allocating a payment from one workspace to an invoice in another returns 404 and creates no allocation. A building in the same workspace but on a different property returns 400 and does not include that property's name. Residents cannot list other members, change roles, edit the workspace, view properties, or read another resident's profile or stay. A resident of one workspace can own another without gaining management rights in the first. Query-string workspace ids are ignored. Login and registration CSRF is enforced when the client enforces cookies; DRF would otherwise skip that check for anonymous posts.

Role permissions are checked on the server. Hiding a button is not authorization. Resident memberships do not include workspace-management permissions. Finance can read properties, residents, and occupancy, and cannot change them. Finance and the owner can write invoices and payments. A property manager can read money records and cannot write them. Maintenance can read properties, residents, and occupancy, and cannot read or write money. Only an owner or property manager can mark a space unavailable for maintenance or record a stay. A resident cannot open the availability board, the arrears list, or a report, and cannot read another resident's invoice, payment, or maintenance request. Maintenance staff cannot read a request assigned to someone else, and their maintenance report does not include that count. The billing write API rejects `provider`, `provider_reference`, and `provider_status`. Maintenance writes reject attachment fields. CSV cells that look like formulas are prefixed.

An owner inviting by email is told when no active account uses that address. That reveals whether the email is registered. There is no mailer yet, so the invite cannot be blind. The response does not include the invitee's other workspaces.

Workspace deletion removes that workspace and its memberships. It does not remove the user account. Audit rows for the deletion remain without a workspace foreign key. Audit rows are not on the product API.

## Files

No upload endpoint exists. Resident documents and other private files will use Cloudflare R2 (S3-compatible) in a private bucket. The app will open an object only with a short-lived signed URL it generates. The endpoint, bucket, and keys come from `FILE_STORAGE_*` environment variables through `config.storage.file_storage_config`. Nothing in the settings hardcodes an R2 host or credential. Local development still uses `FileSystemStorage` under `backend/media/`, which is gitignored, until an upload slice is built. That disk is not the production store. See ADR-012.

## Admin

`/admin/` is Django's admin for platform superusers. `config.admin_access` requires `is_active`, `is_staff`, and `is_superuser`. A workspace owner, and a staff user who is not a superuser, is redirected away. The admin index title says it is platform operations. Create the first operator locally with `manage.py createsuperuser`. Do not commit that password. Audit events cannot be added, edited, or deleted in the admin.

## Backups

Planned approach, not automated (ADR-011). The product owner confirmed this on 2026-10-23:

1. Nightly `pg_dump` of the application database on the VPS.
2. Encrypt the dump before it leaves the machine. Keep the key off the VPS disk that holds PostgreSQL.
3. Upload the encrypted dump to a Cloudflare R2 bucket that is separate from the private file bucket. Use access keys that the application process does not have. The app's file keys must not be able to read or delete backups.
4. Retain about 30 days, then expire the objects at the storage provider.
5. Restore one dump into an empty database before launch. Confirm `manage.py showmigrations` and `GET /api/v1/health/ready/`. Repeat that drill on a schedule after launch.

The backup endpoint and keys are operator environment variables (`BACKUP_S3_ENDPOINT_URL`, `BACKUP_S3_BUCKET`, `BACKUP_S3_ACCESS_KEY_ID`, `BACKUP_S3_SECRET_ACCESS_KEY`). Django does not load them. A copy on the same disk is not a backup. No cron, script, or workflow in this repository performs the dump, encryption, upload, or restore. A restore drill has not been run.

## Deploy checklist

With production settings and a strong secret, `manage.py check --deploy` completes with warning `security.W004` only. Test settings are not the deploy configuration: they use locmem email and insecure cookie flags on purpose, and `check --deploy` against them reports those choices.

## Not done

- Login throttling
- Automated backups and a tested restore
- An upload endpoint and the S3 storage package. The R2 bucket decision is recorded; files are not stored there yet
- HSTS
- A real email provider, including blind membership invites
- A Paystack webhook and signature check. The gateway is chosen and not connected.
- Mobile token storage
