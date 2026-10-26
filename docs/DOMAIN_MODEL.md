# Domain model

`accounts.User`, `organizations.Workspace`, `organizations.Membership`, `organizations.AuditEvent`, the property tables, residents, occupancy, billing, and maintenance tables exist. Reports are queries, not tables. The remaining entities are the model later slices must preserve. Do not add them until the slice that uses them.

## Implemented

### User

Table: `accounts_user`.

- `id` UUID primary key
- `email` unique, stored lowercase, used as the login identifier
- Case-insensitive uniqueness is also enforced by `accounts_user_email_ci_unique` on `lower(email)`
- `first_name`, `last_name`
- `is_active`
- `is_staff` — platform admin flag, not a workspace role
- `is_superuser`, `groups`, `user_permissions` — Django admin permissions
- `password` stored with Django's password hashers
- `date_joined`, `last_login`

Invariants that are tested: email is normalized; a mixed-case duplicate cannot be inserted even when `save()` is bypassed; common passwords are rejected; staff and superuser default off; superuser creation must set both flags.

A user is not a resident profile and is not a workspace. Linking a person to a workspace is a membership.

### Workspace

Table: `organizations_workspace`.

- `id` UUID primary key
- `name`
- `currency_code` — three uppercase letters, checked in the model and by a database check
- `timezone` — IANA name, checked with the zone database
- `status` — `active` or `suspended`. Platform admin changes this. The product API does not.
- `plan_code` — short label, default `placeholder`, matching `^[a-z][a-z0-9_]{0,31}$`. Platform admin changes this. The product API returns it and rejects a client write. No feature check reads it (ADR-019).
- `created_at`, `updated_at`

One currency per workspace (ADR-007).

### Membership

Table: `organizations_membership`.

- `id` UUID primary key
- `workspace_id`, `user_id`
- `role` — one of `owner`, `property_manager`, `finance`, `maintenance`, `resident`
- `is_active`
- `created_at`, `updated_at`
- Unique on (`workspace`, `user`)

Deactivation sets `is_active` false. It does not delete the row. The last active owner cannot be demoted or deactivated.

### Audit event

Table: `organizations_auditevent`. Written for workspace, membership, resident contact, billing, and maintenance changes. Maintenance actions are `maintenance.created`, `maintenance.assigned`, `maintenance.status_changed`, and `maintenance.cost_recorded`. A note-only update is a history row and does not add an audit action. Not returned by the product API. Platform admin can read the rows and cannot edit them. Deleting a workspace sets `workspace_id` null and keeps the event. Property changes are not audit events. There is no payload column.

### Property

Table: `properties_property`.

- `id` UUID primary key
- `workspace_id`
- `name` — unique per workspace, case-insensitive
- `address` — optional
- `created_at`, `updated_at`

### Building

Table: `properties_building`. Optional grouping on a property.

- `id` UUID primary key
- `workspace_id` — must match the property's workspace
- `property_id`
- `name` — unique per property, case-insensitive
- `created_at`, `updated_at`

### Floor

Table: `properties_floor`. Optional. A floor may name a building or sit on the property.

- `id` UUID primary key
- `workspace_id`
- `property_id`
- `building_id` — null when the floor is not inside a building
- `name` — unique for the same property and building, including when the building is null
- `created_at`, `updated_at`

### Space

Table: `properties_space`. A rentable whole unit or room.

- `id` UUID primary key
- `workspace_id`
- `property_id`
- `building_id`, `floor_id` — both optional. A floor's building must match the space's building.
- `name` — unique for the same property, building, and floor
- `kind` — `unit` or `room`
- `availability` — `active`, `inactive`, or `unavailable`
- `block_reason` — empty, or `maintenance` only when availability is `unavailable`. Unavailable plus `maintenance` is the maintenance block.
- `created_at`, `updated_at`

A whole unit does not have beds. Changing a room to a unit while beds exist is rejected.

### Bed

Table: `properties_bed`. Optional, and only on a room.

- `id` UUID primary key
- `workspace_id`
- `space_id` — the room
- `name` — unique per room, case-insensitive
- `availability` and `block_reason` — same rules as a space
- `created_at`, `updated_at`

Deleting a property deletes its buildings, floors, spaces, and beds. It does not delete rows in another workspace.

## Resident

Table: `residents_resident`. A contact profile in one workspace. It is not a login and not a stay.

- `id` UUID primary key
- `workspace_id`
- `user_id` — optional. When set, that user has the resident role in this workspace, and only one profile in the workspace points at them.
- `first_name`, `last_name`
- `email` — optional contact address, stored lowercased. Not required to match the login.
- `phone` — optional
- `created_at`, `updated_at`

Emergency contacts, identity numbers, and dates of birth are not stored.

## Booking

Table: `bookings_booking`. A reservation. The occupied space lives on the assignment.

- `id` UUID primary key
- `workspace_id`
- `resident_id`
- `status` — `confirmed`, `converted`, or `cancelled`
- `start_date`, `end_date` — `end_date` is the last reserved day and may be null for an open-ended reservation
- `created_at`, `updated_at`

## Tenancy

Table: `tenancies_tenancy`. The commercial terms for one resident. Not an invoice and not a room.

- `id` UUID primary key
- `workspace_id`
- `resident_id`
- `booking_id` — optional, set when the agreement came from a reservation
- `status` — `active`, `ended`, or `cancelled`
- `start_date`, `end_date` — expected last day; `end_date` may be null
- `ended_on` — set when the agreement ends
- `fee_amount`, `fee_period` (`night`, `week`, or `month`), `deposit_amount`, `currency_code` — the agreed figures, copied currency, not a balance
- `created_at`, `updated_at`

## Assignment

Table: `tenancies_assignment`. One stay in a unit, a whole room, or a bed.

- `id` UUID primary key
- `workspace_id`
- `resident_id`
- `space_id`
- `bed_id` — null means the whole space
- `booking_id`, `tenancy_id`, `transferred_from_id` — optional links. A transfer points at the stay it continued.
- `status` — `confirmed`, `active`, `checked_out`, `cancelled`, or `transferred`
- `start_date`, `end_date` — inclusive. Null `end_date` is open-ended.
- `created_at`, `updated_at`

## Occupancy block

Table: `tenancies_occupancyblock`. A derived hold, not the history. Rows exist only while the assignment is confirmed or active.

- `id` UUID primary key
- `assignment_id`, `workspace_id`, `space_id`
- `bed_id` — null for a whole-space hold
- `period` — PostgreSQL `daterange`. Fixed stays are inclusive. Open stays are lower-inclusive and unbounded.

Exclusion constraints `block_bed_no_overlap` and `block_space_no_overlap` reject overlapping holds. See ADR-016.

## Invoice

Table: `billing_invoice`. A charge document. The tenancy fee is not this row until staff copy it onto lines.

- `id` UUID primary key
- `workspace_id`, `resident_id`, optional `tenancy_id`
- `reference` — `INV-0001` style, unique per workspace, assigned by the server
- `issued_on`, `due_on` — due on or after the issue date
- `currency_code` — copied from the workspace
- `status` — `issued` or `void`
- `recorded_by_id`, `created_at`, `updated_at`

Outstanding amount is not a column. It is the line total minus active allocations, or zero when void.

## Invoice line

Table: `billing_invoiceline`. Immutable after insert.

- `invoice_id`, `position`
- `description`
- `quantity`, `unit_amount`, `line_total` — decimals. `line_total` is `quantity * unit_amount` stored on the row. The client does not send it.

## Invoice void

Table: `billing_invoicevoid`. One row per voided invoice: `reason`, `voided_on`, `recorded_by_id`.

## Payment

Table: `billing_payment`. Money the workspace received.

- `id` UUID primary key
- `workspace_id`, `resident_id`
- `reference` — `PAY-0001` style, unique per workspace
- `amount`, `currency_code`, `paid_on`
- `method` — `cash`, `bank_transfer`, `mobile_money`, `card`, or `other`
- `external_reference` — optional note such as a slip number. Not a gateway id.
- `provider`, `provider_reference`, `provider_status` — all null for a manual payment. A later Paystack row stores the provider name, Paystack's reference, and Paystack's status here. `pay_provider_reference_unique` allows one reference per workspace and provider when the reference is present.
- `status` — `recorded` or `void`. This is not `provider_status`.
- `recorded_by_id`, `created_at`, `updated_at`

Unallocated amount is not a column. It is the payment amount minus active allocations and refunds, or zero when void.

## Payment void, allocation, reversal, refund

- `billing_paymentvoid` — one row per voided payment.
- `billing_allocation` — how much of one payment applies to one invoice. The row is kept.
- `billing_allocationreversal` — one row per reversed allocation.
- `billing_refund` — money returned from the unallocated remainder.

`billing_documentcounter` stores the next invoice and payment numbers for a workspace.

### Maintenance request

Table: `maintenance_maintenancerequest`. A work order. It is not an invoice and it does not change availability.

- `id` UUID primary key
- `workspace_id`
- `property_id`, `space_id`, `bed_id`, `resident_id` — optional. A bed requires a space. A space requires a property. Each parent must be in the same workspace.
- `reported_by_id`, `assignee_id` — users. Set null if that user is deleted.
- `reference` — `MNT-0001` onward, unique per workspace
- `description`
- `priority` — `low`, `normal`, `high`, or `urgent`
- `status` — `open`, `assigned`, `in_progress`, `completed`, or `cancelled`. Open has no assignee. Assigned, in progress, and completed require one. Completed requires a completion note.
- `completion_note`
- `cost_amount` — nullable decimal, 19 digits and 4 fractional digits, zero or greater. The latest cost only.
- `currency_code` — copied from the workspace
- `created_at`, `updated_at`

`maintenance_requestcounter` stores the next reference number for a workspace.

### Maintenance update

Table: `maintenance_maintenanceupdate`. One row when a request is filed or changed. This is the status history.

- `workspace_id` must match the request
- `request_id`
- `actor_id`
- `status_before`, `status_after`
- `note`
- `cost_amount` — set only on the update that recorded a new cost
- `assignee_id` — the assignee after that change
- `created_at`

Deleting a request is not offered. A request protects its property, space, bed, resident, and workspace from deletion.

## Planned entities

These names are directional. A later slice can rename one if `docs/DOMAIN_MODEL.md` and the migration land together.
- **Fee schedule** — how a tenancy is priced over time. The tenancy fee can be copied onto an invoice, but nothing generates the next period.
- **Deposit ledger** — when deposits are tracked beyond an invoice line. Not a mutable balance column.
- **Document** — metadata and a storage key for a private file. Not a public path. Maintenance requests do not store one yet.
- **Notification** — Phase 02.
- **SaaS subscription** — a priced plan and a charge. Phase 01 only stores `status` and `plan_code`. Never mixed with resident payments.

## Invariants

Workspace, membership, property, resident, occupancy, invoice, payment, maintenance, and report rules below are enforced.

**Tenant.** A row from workspace A cannot be stored on a parent from workspace B. The check happens on the server, in the same transaction as the write. Property, building, floor, space, and bed writes set `workspace_id` from the active membership. A parent id outside that workspace is a 404 and creates nothing.

**Occupancy.** Confirmed and active assignments of the same rentable space must not overlap. The end date is inclusive: the stay covers `[start, end]`, and the space is free on the next day. A null end means open-ended. Two ranges overlap when `new_start <= existing_end` and `new_end >= existing_start`. Cancelled, checked-out, and transferred assignments do not block the space. A whole-room stay also holds every bed in that room, and a bed stay holds the bed so the room cannot be taken whole. Transfers append a new row and close the previous row on the day before the move. See ADR-008 and ADR-016.

**Membership.** A membership cannot be moved to another workspace. Creating one rejects a client-supplied id and rejects a `workspace_id` that is not the active workspace. Residents do not receive management permissions, including in a workspace where they are a resident and also own a different workspace. Residents also cannot view or manage properties.

**Properties.** A whole unit has no beds. A bed cannot be added to a unit. A room can have zero beds. Availability `unavailable` with block reason `maintenance` is how staff block a space or bed for maintenance. Owner and property manager are the only roles that can write property records. Finance and maintenance can read them.

**Money.** No binary floats. No edited "balance" column. Paid and outstanding amounts come from invoice lines and allocations. An allocation cannot exceed the payment or the amount still outstanding. Overpayment stays unallocated. Corrections are reversals, voids, refunds, or new documents. Currency is copied onto the monetary row and cannot change after an invoice or payment exists. A manual payment may use `card`. Provider fields stay empty until Phase 02 writes a Paystack charge. Resident payments and SaaS subscription payments are different aggregates. See ADR-007 and ADR-009.

**Residents.** A resident membership cannot perform workspace management or read other residents. A resident profile is separate from the membership. The profile stores a name and optional phone, email, and login link. A resident can read their own invoices, payments, and maintenance requests, and can file a request. Staff can file a request for a resident. A profile with occupancy, billing, or a maintenance request cannot be deleted.

**Maintenance.** Status history is a `MaintenanceUpdate` row, not a rewritten status with no past. Maintenance staff do not see another assignee's queue. A request does not mark a space or bed unavailable. The maintenance block on the space or bed remains a property-screen action. A cost on a request is not posted to an invoice.

**Reports.** Occupancy, arrears, collections, and maintenance totals are computed from the current rows for the active workspace. They are not stored. A role that cannot read the underlying records receives 403, or, for the maintenance role on the maintenance report, a count of only the requests that role can open. CSV uses that same set.

## Identifier and time conventions

Tenant-owned primary keys should be UUIDs, matching the user model, so sequential ids do not leak another tenant's volume. Timestamps are timezone-aware UTC. Business dates are `DateField` values, not datetimes.
