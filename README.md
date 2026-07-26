# SupportX — Day 1: Auth + RBAC

## Setup
```
pip install -r requirements.txt
python seed.py          # creates 4 demo users (customer/agent/team_lead/admin), password: pass123
uvicorn app.main:app --reload
```

Server runs at http://localhost:8000
Interactive API docs: http://localhost:8000/docs  (great for demoing to evaluators — shows all endpoints live)

## Demo logins (created by seed.py)
| Role | Email | Password |
|---|---|---|
| Customer | customer@supportx.com | pass123 |
| Agent | agent@supportx.com | pass123 |
| Team Lead | teamlead@supportx.com | pass123 |
| Admin | admin@supportx.com | pass123 |

## What's working
- POST /auth/signup — public signup (always creates a Customer, role is never accepted from the client)
- POST /auth/login — returns JWT with role baked in
- GET /auth/me — frontend uses this to decide which dashboard to redirect to
- POST /auth/admin/create-user — Admin-only, creates Agent/Team Lead/Admin accounts
- require_role() dependency in app/auth.py — reusable RBAC guard for every future endpoint

## Database
Uses SQLite (supportx.db) by default so it runs with zero setup — no PostgreSQL
install needed for the demo. To switch to real PostgreSQL later, set the
DATABASE_URL environment variable before running.

## Next (Day 2)
Build the 4 role-based frontend pages and wire up the redirect after login.

## Day 2: Frontend

Open `frontend/index.html` directly in your browser (double-click it) while
uvicorn is still running in a separate terminal. It's a single HTML file with
a login screen and 4 role-based dashboards (Customer, Agent, Team Lead, Admin).

- Click any of the 4 demo account buttons on the login screen to autofill credentials
- After login, the sidebar navigation changes based on your role
- Page content is currently placeholder text — real ticket/chatbot/SLA data
  gets wired in on Day 3 onward
