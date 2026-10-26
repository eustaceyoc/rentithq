# API contract

Base path: `/api/v1/`. Trailing slashes are required. The contract below is what the code does, plus conventions Phase 01 must follow. Endpoints marked planned do not exist.

## Authentication

- Default: session cookie, CSRF on unsafe methods.
- Default permission: authenticated user.
- Anonymous access to a protected view: HTTP 403, code `not_authenticated`.
- Health probes opt out of authentication and permission checks.
- `GET /api/v1/auth/csrf/` returns `{"csrfToken": "..."}` and sets the CSRF cookie. Anonymous.
- `POST /api/v1/auth/register/` with `email`, `password`, optional `first_name` and `last_name`. Creates a non-staff user, signs them in, and returns the session payload. `is_staff` and `is_superuser` in the body are ignored.
- `POST /api/v1/auth/login/` with `email` and `password`. Unknown email and wrong password return the same 400 body. It does not include the password.
- `POST /api/v1/auth/logout/` returns 204.
- `GET /api/v1/auth/session/` returns the signed-in user and that user's active memberships only.
- Login and registration enforce CSRF even though the caller is anonymous.
- Django admin at `/admin/` is separate and requires `is_staff` and `is_superuser`.

`X-Workspace-Id` selects among the caller's active memberships. It does not grant access. One active membership may omit it. Several memberships without it return 400 `workspace_required`. A selector that is missing, malformed, or not one of the caller's active memberships returns 404 `not_found`. The body does not include the other workspace's name. A `workspace_id` query parameter is ignored. See ADR-005.

A suspended workspace still appears to its members. Membership calls and workspace edits then return 403 `workspace_unavailable`. Someone who is not a member still receives 404.

## Error shape

All DRF error responses use:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request could not be processed.",
    "details": {}
  }
}
```

| HTTP | `code` |
| --- | --- |
| 400 | `validation_error` or `workspace_required` |
| 401 or session-auth failure rewritten to 403 | `not_authenticated` |
| 403 | `permission_denied` or `workspace_unavailable` |
| 404 | `not_found` |
| 405 | `method_not_allowed` |
| 429 | `throttled` |
| 500 | `server_error` |

`details` carries field errors for validation. For 500, `details` is `{}` and the body does not include the exception text. 404 copy stays generic so it does not reveal another workspace's records.

## Pagination

Page number pagination. `page` starts at 1. `page_size` defaults to 25 and cannot exceed 100. Workspace and membership lists use it. The body is `{"count", "next", "previous", "results"}`.

## Money and dates

Money fields are JSON strings with exactly four fractional digits, for example `"10.5000"`. They are not JSON numbers. Currency is a separate uppercase three-letter code. Datetimes are ISO 8601 in UTC. Date-only fields are `YYYY-MM-DD`.

## Implemented endpoints

### `GET /api/v1/health/`

Liveness. Does not query the database.

```json
{"status": "ok", "service": "rentithq-api"}
```

HTTP 200. `Cache-Control: no-store`. Other methods return 405 and the error shape.

### `GET /api/v1/health/ready/`

Readiness. Runs `SELECT 1`.

```json
{"status": "ok", "database": "ok"}
```

If the database is unavailable: HTTP 503 and `{"status": "unavailable"}`. The body does not include the driver error.

## Session payload

`GET /api/v1/auth/session/`, and the login and registration responses, use:

```json
{
  "user": {"id": "uuid", "email": "ada@example.com", "first_name": "Ada", "last_name": "Lovelace"},
  "memberships": [
    {
      "id": "uuid",
      "role": "owner",
      "workspace": {
        "id": "uuid",
        "name": "Ada House",
        "currency_code": "GHS",
        "timezone": "Africa/Accra",
        "status": "active",
        "plan_code": "placeholder"
      }
    }
  ]
}
```

`is_staff` and `is_superuser` are not in this payload.

## Workspaces

`GET /api/v1/workspaces/` lists workspaces where the caller has an active membership. It does not require `X-Workspace-Id`.

`POST /api/v1/workspaces/` body: `name`, `currency_code` (uppercase, three letters), optional `timezone` (IANA, default `UTC`). The caller becomes the only owner. `status` and `plan_code` cannot be set here. `plan_code` defaults to `placeholder` (ADR-019).

`GET /api/v1/workspaces/<uuid>/` returns the workspace when the caller is an active member. Any other id, including a non-UUID, is 404 JSON.

`PATCH /api/v1/workspaces/<uuid>/` updates `name`, `currency_code`, or `timezone`. Owner only. Other members receive 403. Non-members receive 404. `status`, `plan`, and `plan_code` are rejected. Django admin can change `plan_code`. No feature check reads it.

`DELETE /api/v1/workspaces/<uuid>/` deletes that workspace and its memberships. Owner only. Response 204. A non-member's delete does not delete anything and returns 404. A workspace that still has occupancy history, billing history, or a maintenance request is refused and stays.

## Memberships

These routes require the active-workspace rules above.

`GET /api/v1/memberships/` lists active members. Residents receive only their own row. Staff roles and owners receive the workspace roster.

`POST /api/v1/memberships/` body: `email`, `role`. Owner only. The email must already belong to an active account. Optional `workspace_id` must equal the active workspace or the request is 400 and no row is written. A client-supplied `id` is rejected. An inactive membership for that person in the same workspace is reactivated. The response user object is `id`, `email`, `first_name`, `last_name`.

`GET /api/v1/memberships/<uuid>/` returns one visible membership. A membership from another workspace, or another person's membership requested by a resident, is 404.

`PATCH /api/v1/memberships/<uuid>/` body: `role`. Owner only. `workspace_id`, `user`, and `id` cannot be changed. The last active owner cannot be given another role.

`DELETE /api/v1/memberships/<uuid>/` deactivates the membership. It does not delete the user. Owner only. The last active owner cannot be deactivated. Response 204. A cross-workspace id returns 404 and stays active.

Roles: `owner`, `property_manager`, `finance`, `maintenance`, `resident`.

## Properties

These routes require the active-workspace rules above. Every row is stored with the active workspace. A client `workspace_id` must match that workspace on create and cannot be changed on update. A client-supplied `id` is rejected. Query-string `workspace_id` is ignored.

Roles: owner and property manager can write. Finance and maintenance can read. Residents receive 403 `permission_denied` and the body does not include property names. A parent id from another workspace, including attaching a space to another workspace's property, returns 404 `not_found` and creates nothing. A non-UUID path id returns JSON 404.

`GET` and `POST /api/v1/properties/`, plus `GET`, `PATCH`, and `DELETE /api/v1/properties/<uuid>/`.

Create body: `name`, optional `address`. Names are unique per workspace, ignoring case.

`GET` and `POST /api/v1/buildings/`, plus `GET`, `PATCH`, and `DELETE /api/v1/buildings/<uuid>/`.

Create body: `property_id`, `name`. `GET` accepts `property_id`. A property id outside the workspace is 404, not an empty page. Buildings are optional.

`GET` and `POST /api/v1/floors/`, plus `GET`, `PATCH`, and `DELETE /api/v1/floors/<uuid>/`.

Create body: `property_id`, `name`, optional `building_id`. `GET` accepts `property_id` and `building_id`. A building on a different property in the same workspace is 400. Floors are optional.

`GET` and `POST /api/v1/spaces/`, plus `GET`, `PATCH`, and `DELETE /api/v1/spaces/<uuid>/`.

Create body: `property_id`, `name`, `kind` (`unit` or `room`), optional `building_id` and `floor_id`, optional `availability` (`active`, `inactive`, `unavailable`) and `block_reason` (empty or `maintenance`). `GET` accepts `property_id`, `building_id`, and `floor_id`. A floor must belong to the same building as the space. A whole unit does not need beds. `PATCH` that sets `kind` to `unit` while beds exist is 400 and changes nothing.

`block_reason` may be `maintenance` only when `availability` is `unavailable`. That pair is the maintenance block. `unavailable` with an empty reason is a generic block. Any other pair is 400. Sending `availability` of `active` or `inactive` without a reason clears `block_reason`.

`GET` and `POST /api/v1/beds/`, plus `GET`, `PATCH`, and `DELETE /api/v1/beds/<uuid>/`.

Create body: `space_id`, `name`, and the same availability fields. The space must be a room in the active workspace. A unit returns 400 and creates no bed. `GET` accepts `space_id`. A room may have no beds. Availability rules match spaces.

`DELETE` on any of these returns 204. Deleting a property deletes its buildings, floors, spaces, and beds in that workspace only.

## Residents, bookings, and occupancy

Every endpoint below calls `resolve_active_membership` and then checks the role. Owner and property manager may write. Finance and maintenance may read. A resident may read only their own profile, tenancies, and stays. A resident may `PATCH` only `phone` and `email` on the profile linked to their login. Any other field is 400 and changes nothing. Another resident's profile is 404. Availability is staff-only. A resident, space, or bed from another workspace is 404 and creates no row. Client-supplied `id`, `workspace_id`, and status are rejected.

Dates are inclusive. `end_date` is the last occupied day and may be null. Money fields are decimal strings, as in ADR-007.

`GET` and `POST /api/v1/residents/`, plus `GET`, `PATCH`, and `DELETE /api/v1/residents/<uuid>/`.

Create body: `first_name`, `last_name`, optional `email`, `phone`, and `account_email`. `account_email` links a user who already has the resident role in this workspace. Staff `PATCH` can change those fields. A resident `PATCH` can change only `phone` and `email`, and only on their linked profile. A real change writes `resident.phone_updated` or `resident.email_updated`. `DELETE` returns 204 only when the profile has no booking, tenancy, stay, invoice, or payment. Otherwise it is 400 and the row remains.

`GET` and `POST /api/v1/bookings/`, plus `GET` and `PATCH /api/v1/bookings/<uuid>/`.

Create body: `resident_id`, `space_id`, `start_date`, optional `end_date` and `bed_id`. This creates a confirmed booking and a confirmed assignment. `POST /api/v1/bookings/<uuid>/cancel/` releases the hold and keeps the row. `POST /api/v1/bookings/<uuid>/convert/` body is `fee_amount`, `fee_period` (`night`, `week`, or `month`), optional `deposit_amount`, and optional `check_in`. It returns the tenancy. A conflicting stay or a maintenance block is 400 and creates nothing.

`GET` and `POST /api/v1/tenancies/`, plus `GET` and `PATCH /api/v1/tenancies/<uuid>/`.

Create body: `resident_id`, `start_date`, `fee_amount`, `fee_period`, optional `end_date`, `deposit_amount`, `space_id`, `bed_id`, and `check_in`. `POST /api/v1/tenancies/<uuid>/end/` body is `ended_on`. `POST /api/v1/tenancies/<uuid>/cancel/` is only for an agreement that has not yet got occupancy history. An agreement with history must be ended.

`GET` and `POST /api/v1/assignments/`, plus `GET` and `PATCH /api/v1/assignments/<uuid>/`.

`PATCH` changes dates. It does not move the space. `POST /api/v1/assignments/<uuid>/check-in/`, `/check-out/` (`end_date`), `/cancel/`, and `/transfer/` (`space_id`, `start_date`, optional `bed_id`). Transfer returns 201 for the new stay. The old stay stays, with status `transferred` and an end date of the day before the move. Cancel is only for a confirmed stay. An active stay is checked out.

`GET /api/v1/availability/?on=YYYY-MM-DD` returns one row per space and one row per bed. Optional `property_id` limits the page. `state` is `free`, `occupied`, `partly_occupied`, or `unavailable`. `partly_occupied` means a room is not free to book as a whole because a bed is taken. Occupied rows include `resident_name`.

## Invoices, payments, and arrears

Every endpoint below calls `resolve_active_membership` and then checks the role. The owner and finance may write. A property manager may read invoices, payments, receipts, and arrears, and receives 403 on a write. Maintenance receives 403 on every billing endpoint, and the body does not include invoice or payment references. A resident may read only invoices and payments for their own profile, and receives 404 for someone else's. A resident receives 403 on arrears and on every write. A row from another workspace is 404 and creates nothing. Allocating a payment in one workspace to an invoice in another is 404.

Money fields are decimal strings with four fractional digits. The server rejects a float. The client cannot send `reference`, `status`, `currency_code`, a total, an outstanding amount, a balance, or `provider`, `provider_reference`, or `provider_status`. There is no `PATCH` or `DELETE` of a money row. The web UI and print views show the currency's usual minor units (two for GHS) and still submit four-place strings. Rounding for display is half away from zero. Storage and this API stay at four places (ADR-007).

`GET` and `POST /api/v1/invoices/`, plus `GET /api/v1/invoices/<uuid>/`.

Create body: `resident_id`, `issued_on`, `due_on`, and `lines` (`description`, `quantity`, `unit_amount`). Alternatively send `from_tenancy: true`, `tenancy_id` or `booking_id`, and optional `include_deposit`. The fee and deposit are copied onto lines. A reservation that has not been converted returns 400 and creates nothing. Manual lines and `from_tenancy` together are rejected. The response includes `total_amount`, `allocated_amount`, and `outstanding_amount`. Outstanding is zero when the invoice is void.

`POST /api/v1/invoices/<uuid>/void/` body is `reason` and `voided_on`. An invoice with an active allocation cannot be voided until that allocation is reversed.

`GET` and `POST /api/v1/payments/`, plus `GET /api/v1/payments/<uuid>/`.

Create body: `resident_id`, `amount`, `paid_on`, `method` (`cash`, `bank_transfer`, `mobile_money`, `card`, or `other`), and optional `external_reference`. The detail response is the receipt: allocations, refunds, unallocated amount, and the recording user's email. `provider`, `provider_reference`, and `provider_status` are null on a manual payment. They are reserved for a later Paystack charge (ADR-009). Sending them is 400 and creates nothing.

`POST /api/v1/payments/<uuid>/void/` body is `reason` and `voided_on`. A payment with an active allocation or a refund cannot be voided.

`POST /api/v1/payments/<uuid>/refunds/` body is `amount`, `refunded_on`, `reason`, and optional `external_reference`. The amount cannot exceed the unallocated remainder. Reverse an allocation before refunding money that was applied to an invoice.

`POST /api/v1/allocations/` body is `payment_id`, `invoice_id`, and `amount`. The amount cannot exceed the payment's unallocated remainder or the invoice's outstanding amount. The payment and invoice must belong to the same resident. `POST /api/v1/allocations/<uuid>/reverse/` body is `reason` and `reversed_on`. A reversal cannot be reversed again.

`GET /api/v1/arrears/?on=YYYY-MM-DD` returns issued invoices in the active workspace with `due_on` on or before that date and an outstanding amount greater than zero. Future, fully paid, and void invoices are excluded. `on` is required.

Recording a payment does not call Paystack. There is no webhook.

## Maintenance requests

Every endpoint below calls `resolve_active_membership` and then checks the role. See ADR-017.

`GET` and `POST /api/v1/maintenance-requests/`, plus `GET` and `PATCH /api/v1/maintenance-requests/<uuid>/`. There is no `DELETE`. Lists accept `status` and `priority`. Page size follows the standard pagination, default 25 and maximum 100.

The owner, property manager, and finance see every request in the workspace. Finance can file one and receives 403 on `PATCH`. The owner and property manager can assign. An assignee must be an active owner, property manager, or maintenance member of this workspace. The same error is returned if that user is missing, has another role, or belongs to another workspace. Maintenance staff see and update only requests assigned to them, plus requests they filed that are still unassigned. Another request is 404 and is omitted from counts. They cannot set the assignee, description, priority, place, or resident. A resident files and reads only requests for the profile linked to their login. `PATCH` on their own request is 403. Another resident's request is 404. A request in another workspace is 404 and creates nothing.

Staff create body: `property_id`, `description`, `priority` (`low`, `normal`, `high`, or `urgent`), optional `space_id`, `bed_id`, `resident_id`, and, for an owner or property manager, optional `assignee_id`. The space must be on that property. The bed must be in that space. A resident may omit the place, or send a `space_id` on their own confirmed or active stay. If they send `bed_id`, it must be their bed, or any bed in the room when the stay is for the whole room. The server sets `property_id` from that space. `resident_id`, when a resident sends one, must be their own profile.

The server sets `reference` (`MNT-0001` onward, per workspace), `currency_code`, and `status`. Create rejects `status`, `cost_amount`, and `completion_note`. An assignee on create sets the status to `assigned`. Otherwise the status is `open`.

`PATCH` can change `description`, `priority`, `status`, `assignee_id`, `note`, `completion_note`, and `cost_amount`. It cannot change the place, resident, reference, or currency. Status moves for maintenance staff are open to cancelled, assigned to in progress or cancelled, and in progress to completed or cancelled. Owners and property managers can also move open to assigned or in progress, and assigned back to open. Open has no assignee. Assigned, in progress, and completed require one. Completed requires `completion_note`. A cost is a decimal string, zero or greater, in the workspace currency. It is the latest figure, stored on the request and on that history row. It is not an invoice. A float is rejected.

Each create or update writes one `MaintenanceUpdate`. The list and detail responses include those rows: `status_before`, `status_after`, `note`, `cost_amount`, and the assignee at that time. `location_blocked` is true when the named bed or space is already unavailable with block reason `maintenance`. Creating, updating, or completing a request does not change that block.

`photo`, `photos`, `attachment`, `attachments`, `file`, and `document` are rejected. There is no upload endpoint.

## Reports

Read-only. Every report calls `resolve_active_membership`. Another workspace's rows are not included. `export=csv` uses the same query and the same role check. Any other `export` value is 400. The CSV is `text/csv` with `Content-Disposition: attachment` and `Cache-Control: no-store`. A cell that starts with `=`, `+`, `-`, `@`, tab, or carriage return is prefixed so a spreadsheet does not treat it as a formula. Money in JSON and CSV stays at four decimal places. See ADR-018.

`GET /api/v1/reports/occupancy/?on=YYYY-MM-DD&within_days=30`. `within_days` is 1 to 366 and defaults to 30. Owner, property manager, finance, and maintenance can read it. A resident receives 403. The body counts spaces by kind (`unit`, `room`) and state (`occupied`, `partly_occupied`, `free`, `unavailable`), beds by state, and every property in the workspace, including one with no spaces. It also returns active tenancy and active-resident counts, and upcoming move-outs whose end date falls in the window. The upcoming list returns at most 100 rows. `upcoming_count` is the full number and `upcoming_truncated` is true when the list was cut.

`GET /api/v1/reports/arrears/?on=YYYY-MM-DD`. Owner, property manager, and finance only. Maintenance and residents receive 403, including on `export=csv`, and the body does not include amounts. The total and the per-resident totals reuse the arrears list: issued invoices due on or before that date that still have an outstanding amount.

`GET /api/v1/reports/collections/?from=YYYY-MM-DD&to=YYYY-MM-DD`. The same money roles. The end must be on or after the start, and the span must be 366 days or fewer. Recorded payments with `paid_on` in the range and refunds with `refunded_on` in the range are counted separately. `net_amount` is collected minus those refunds. It can be negative. It is a report figure, not a balance.

`GET /api/v1/reports/maintenance/`. Owner, property manager, and finance receive `scope` `workspace` and every request. Maintenance staff receive `scope` `assigned` and only the requests they can see. Their counts are not the workspace total. A resident receives 403. `open_count` is open plus assigned plus in progress. `by_priority` counts only those non-terminal requests.

## Not implemented

No upload or webhook endpoint exists. Recurring invoices are not generated. Occupancy dates use inclusive end dates (ADR-008 and ADR-016). Private files are configured for Cloudflare R2 and are not uploaded yet. Paystack is the chosen resident mobile-money and card gateway and is not called.
