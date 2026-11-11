# Discord Server Register

A small web service for collecting and sharing Discord server invite links, built with FastAPI and PostgreSQL.

- **Approval-gated accounts.** Users apply with an email and password. An administrator approves or rejects each application, and only approved users can use the service.
- **Verified submissions.** Each invite is looked up on Discord with the **Check** button before it can be submitted. The server's `guild_id`, name, icon and member count are fetched from Discord.
- **No duplicates.** Each Discord server can be registered only once, even when it's submitted with a different invite code.
- **Hidden submitters.** Users can browse every submitted link, but who submitted it is never shown.

## Requirements

- Python 3.10+
- PostgreSQL 14+ (a `docker-compose.yml` is included)

## Setup

```bash
# 1. Configure
cp .env.example .env
#    then edit .env: set POSTGRES_PASSWORD (and the same password in DATABASE_URL),
#    SECRET_KEY and ADMIN_PASSWORD to strong random values

# 2. Start PostgreSQL (or point DATABASE_URL at an existing server)
docker compose up -d

# 3. Install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Run
.venv/bin/uvicorn app.main:app --reload
```

Open <http://localhost:8000>. The tables are created automatically on first start.

> **Security:** `docker-compose.yml` publishes PostgreSQL on `127.0.0.1` only. Don't change it to `5432:5432`. Docker-published ports bypass host firewalls such as ufw, and bots scan the internet for open PostgreSQL servers with weak passwords.

### Configuration (`.env`)

| Variable | Description |
|---|---|
| `POSTGRES_PASSWORD` | Password for the Docker PostgreSQL container. Required by `docker-compose.yml`. |
| `DATABASE_URL` | SQLAlchemy URL, e.g. `postgresql+psycopg2://postgres:<password>@localhost:5432/discord_register` |
| `SECRET_KEY` | Signs the session cookie. Use a long random value in production: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | If both are set, this admin account is created on startup when it doesn't already exist. Changing them later doesn't update an existing account. |

## Usage

1. **Apply.** On the **Register** tab of `/login`, enter an email and password (at least 8 characters).
2. **Approve.** Sign in as the admin and open **User management** (`/admin`). Approve or reject applications under the Pending tab. Rejecting an approved user revokes their access immediately.
3. **Submit links.** Approved users click **+ Submit link** on the links page, then:
   - choose a category and paste an invite link
   - press **Check** to fetch and preview the server's details (Submit stays disabled until the check passes, and the server refuses unchecked invites too)
   - add a brief description and the source where the link was found, then press **Submit**
4. **Browse.** The links page lists every submitted server. You can search it and filter by category.

These invite formats are accepted: `https://discord.gg/CODE`, `https://discord.com/invite/CODE`, `https://discordapp.com/invite/CODE`, or a bare `CODE`.

## API

All endpoints except register and login need an approved session. The `/api/admin` endpoints also need an admin account. Interactive docs are at `/docs`.

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Apply for an account (`email`, `password`) |
| POST | `/api/auth/login` | Sign in. Pending or rejected users get `403`. |
| POST | `/api/auth/logout` | Sign out |
| GET | `/api/auth/me` | The current user |
| GET | `/api/admin/users?status=pending` | List users, optionally filtered by `pending`, `approved` or `rejected` |
| POST | `/api/admin/users/{id}/approve` | Approve a user |
| POST | `/api/admin/users/{id}/reject` | Reject a user, or revoke their access |
| GET | `/api/links/categories` | The available categories |
| GET | `/api/links?category=&q=` | List links, with an optional category filter and text search. Submitters are not included. |
| POST | `/api/links/check` | Look up an invite on Discord and return the server's details and `already_registered` |
| POST | `/api/links` | Submit a link (`category`, `invite`, `description`, `source`). The invite must have been checked in this session within the last 30 minutes. Returns `409` if the server is already registered. |

## How it works

- **Discord lookup.** Uses Discord's public invite endpoint, `GET https://discord.com/api/v10/invites/{code}?with_counts=true`. No bot token is needed.
- **Duplicates.** Detected by `guild_id`, which has a unique constraint in the database. That constraint also catches two people submitting the same server at the same moment.
- **Check before submit.** A successful Check is recorded in the user's signed session cookie. A submission is refused unless its invite was checked by that session within the last 30 minutes. The invite is looked up on Discord again when it's submitted, so an invite that expired in between is caught.
- **Privacy.** Each link stores `submitted_by` for moderation, but the link API never returns it.
- **Sessions.** Sessions are signed cookies, valid for 7 days. The user's approval status is checked again on every request.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

- **Test database:** tests use a separate database named after the one in `DATABASE_URL` plus `_test` (e.g. `discord_register_test`). It's created automatically and emptied before each test. To use a different database, set `TEST_DATABASE_URL`. Your real data is never touched.
- **No network:** Discord is replaced with an in-process fake, so the tests don't need internet access.

## Project structure

```
app/
  main.py          app setup, session middleware, admin bootstrap
  config.py        settings from .env
  database.py      SQLAlchemy engine and session
  models.py        User and Link tables
  schemas.py       request and response models, categories
  security.py      bcrypt password hashing
  deps.py          current-user and admin dependencies
  discord.py       invite parsing and Discord lookup
  routers/
    auth.py        register, login, logout, me
    admin.py       user approval
    links.py       check, submit, list
    pages.py       HTML page routes
  templates/       Jinja2 HTML pages
  static/          CSS and JavaScript
tests/             pytest suite (fake Discord, separate test database)
```
