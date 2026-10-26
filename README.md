# Rent It HQ

Rent It HQ is a property management app I'm building for hostel owners, apartment owners and small property managers. Each business gets its own workspace where they can manage properties, rooms and beds, residents, bookings, invoices, payments and maintenance requests in one place.

## What it does today

- Workspaces with team members and roles (owner, property manager, finance, maintenance, resident)
- Properties, rooms and beds, with availability that respects whole-room and per-bed bookings
- Residents, bookings and tenancies
- Invoices and manually recorded payments (cash, bank transfer, mobile money, card)
- Maintenance requests with priorities, assignment and a status history
- Reports for occupancy, arrears, collections and maintenance, with CSV export
- A dashboard with the key numbers at a glance

## Coming next

- Online mobile money and card payments with Paystack
- Automatic monthly invoices
- Email and SMS reminders
- Document uploads for residents

## Tech stack

- Frontend: React, TypeScript, Vite and Ant Design
- Backend: Python, Django and Django REST Framework
- Database: PostgreSQL
- API base path: `/api/v1/`

## Running it locally

```bash
cp .env.example .env
# Make sure PostgreSQL is running at the DATABASE_URL in .env
# (or start it with: docker compose up -d)
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
npm ci --prefix frontend
make migrate
```

Then start the API and the web app in two terminals:

```bash
cd backend && ../.venv/bin/python manage.py runserver 127.0.0.1:43124
npm run dev --prefix frontend
```

Open http://127.0.0.1:43123 in your browser.

More setup details are in `docs/LOCAL_DEVELOPMENT.md`, and the rest of the `docs/` folder covers the architecture, data model, API and security.

## A few notes

- Tenancy end dates are inclusive, so a room is free again the day after a stay ends.
- Each workspace uses a single currency.
- Amounts are stored with four decimal places and shown with the currency's usual decimals.