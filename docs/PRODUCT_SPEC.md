# Product spec

This document describes the product. Behavior that already exists in code is called out. Everything else is planned and is not implemented. The interface is English only (ADR-015). The product is called Rent It HQ.

## Who it is for

Independent hostel owners, apartment owners, and small property managers. A customer is a workspace, not a single building. One person may belong to more than one workspace.

## What exists now

A person can create an account, sign in, create a workspace, and choose among the workspaces they belong to. The account is not a platform operator. The workspace has one currency, an IANA timezone, an account status, and a plan code that defaults to `placeholder`. The owner can add someone who already has an account and give them one role. Residents can sign in and see only their own membership, profile, agreement, stay, invoices, payments, and maintenance requests. Staff can record properties, residents, reservations, tenancies, occupancy, invoices, manual payments, and maintenance requests, and can open the workspace reports their role allows. The home page also calls `GET /api/v1/health/`. Django admin is limited to platform superusers.

## Roles

| Role | Where it lives | Intent |
| --- | --- | --- |
| Platform operator | `is_staff` and `is_superuser` | Django admin only. Not a workspace role. Superuser access is implemented. |
| Workspace owner | Membership `owner` | Workspace settings and memberships. Implemented. |
| Property manager | Membership `property_manager` | Spaces, residents, and occupancy. Can read invoices, payments, receipts, and arrears, and cannot change them. Can file, triage, and assign maintenance requests. Can read the workspace reports. Can read the workspace and its members. Cannot change workspace settings or memberships. |
| Finance | Membership `finance` | Issues invoices and records payments. Can read properties, residents, and occupancy, and cannot change them. Can file a maintenance request and read every request, and cannot assign or update one. Can read the workspace reports, including arrears and collections. |
| Maintenance staff | Membership `maintenance` | Can read properties, residents, and occupancy, and cannot change them. Cannot view invoices or payments. Can file a request, including for a resident. Sees and updates requests assigned to them, and requests they filed that nobody has taken. Cannot assign or reassign. Occupancy and maintenance reports show only what that role can already see. |
| Resident | Membership `resident` | Own membership, profile, agreement, stay, invoices, payments, and maintenance requests. Can change their own phone and email. Can file a request and cannot change its status. Never sees other residents, properties, arrears, the availability board, or workspace reports. |

A person has one role per workspace. The same person can be finance in one workspace and a resident in another.

## MVP workflows

1. An owner creates a workspace and adds staff who already have accounts. Implemented for the workspace and the membership. There is no email invite.
2. Staff add one or more properties, with optional buildings and floors, whole units, and, where needed, rooms and beds. An apartment does not have to have a bed. A space can be marked unavailable for maintenance. Implemented for owner and property manager writes, and for finance and maintenance as read-only. Residents cannot view these records.
3. Staff add a resident, using only the contact data the workflow needs: name, optional phone, optional email, and an optional link to a resident login. Implemented for owner and property manager. A resident login is still a membership, separate from the profile.
4. Staff record a booking or tenancy and an occupancy with start and end dates. The end date is the last occupied day (ADR-008). The space is free from the next day. Overlapping confirmed or active assignments to the same unit, room, or bed are rejected on the server, including a bed inside a room booked whole. Implemented, including check-in, check-out, cancellation, and transfer. The availability view shows free, occupied, partly occupied, and unavailable.
5. Staff issue an invoice in the workspace currency and record a manual payment: cash, bank transfer, mobile money, card, or other. The outstanding amount is calculated from lines and allocations. Implemented for the owner and finance. A property manager can read the records and cannot change them. Recording a card or mobile-money payment does not charge the resident. Paystack is chosen for that charge and is not connected.
6. Staff print an invoice and a receipt from HTML. Implemented. The browser prints the invoice or the payment receipt. There is no PDF. Amounts on screen and in that printout use the currency's usual decimal places. GHS shows two. The stored value and the API stay at four decimal places.
7. A resident or a staff member records a maintenance request. Staff can file one for a resident. Status changes keep a history row. Implemented. Priorities are low, normal, high, and urgent. Statuses are open, assigned, in progress, completed, and cancelled. There is no photo or document upload. Filing a request does not mark the space unavailable. `location_blocked` only reports a maintenance block that staff already set on the property screen.
8. Staff open occupancy, arrears, collections, and maintenance summaries for the active workspace only. Implemented for the roles in the table above. CSV export uses that same scope. A maintenance login's maintenance report is not the workspace total.

Moving out, cancelling, and transferring rooms keep history. That is implemented.

## Explicitly later

Recurring invoices, email or SMS delivery, the Paystack charge itself, webhooks, native mobile apps, utility billing, accounting exports, public listings, and multi-currency conversion are not part of the MVP. Paystack is the chosen gateway for resident mobile money and card payments (ADR-009) and belongs to Phase 02, with real credentials, webhook signature verification, and idempotency. SaaS subscription billing for the workspace owner is a separate domain. Phase 01 records `Workspace.status` and `Workspace.plan_code`. The plan code does not lock features.

## Out of scope until the owner decides

- A country, currency default, tax regime, or legal tenancy form
- Compliance claims about tenancy, tax, accounting, or privacy law
- A branded product name (the UI says "Rent It HQ" as a placeholder)

## Empty, loading, and error states

The status screen has a loading state, a reachable state, an unhealthy response state, and a failure state that does not display raw server payloads. The account screen has a session check, a signed-out form, an empty workspace state, a workspace chooser, a member list, and error alerts. Property, occupancy, billing, maintenance, and report screens have loading, empty, error, and permission states. Permission failures come from the API. The workspace page links to Properties, Residents, Billing, Maintenance, Reports, and Settings. A resident does not see Properties or Reports. There is no client-side router. The layout is the same card width as before this slice.
