# Discord Server Register

A small web service for collecting and sharing Discord server invite links, built with FastAPI and PostgreSQL.

- **Approval-gated accounts.** Users apply with an email and password. An administrator approves or rejects each application, and only approved users can use the service.
- **Verified submissions.** Each invite is looked up on Discord with the **Check** button before it can be submitted. The server's `guild_id`, name, icon and member count are fetched from Discord.
- **No duplicates.** Each Discord server can be registered only once, even when it's submitted with a different invite code.
- **Private by default.** Each user sees only the links they submitted. Admins see every link and who submitted it.

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
| `DATABASE_URL` | **Required.** SQLAlchemy URL, e.g. `postgresql+psycopg2://postgres:<password>@localhost:5432/discord_register` |
| `SECRET_KEY` | **Required.** Signs the session cookie. At least 32 random characters; the app refuses to start with a missing, short or placeholder value. Generate one with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | `ADMIN_PASSWORD` must be at least 12 characters. If both are set, this admin account is created on startup when it doesn't already exist. Changing them later doesn't update an existing account. |
| `SESSION_HTTPS_ONLY` | Mark the session cookie `Secure` so it's only sent over HTTPS. Default `true`. Browsers also accept it on `http://localhost`; set `false` only to try the app over plain HTTP on another address, such as a LAN IP. |
| `ENABLE_API_DOCS` | Serve the interactive API docs at `/docs`, `/redoc` and `/openapi.json`. Default `false`. |
| `ADMIN_NAME` | Full name for that admin account. Optional; defaults to `Administrator`. |

## Usage

1. **Apply.** On the **Register** tab of `/login`, enter your full name, email and a password (at least 8 characters).
2. **Approve.** Sign in as the admin and open **User management** (`/admin`). Approve or reject applications under the Pending tab. Rejecting an approved user revokes their access immediately.
3. **Submit links.** Approved users click **+ Submit link** on the links page, then:
   - paste an invite link
   - press **Check** to fetch and preview the server's details (Submit stays disabled until the check passes, and the server refuses unchecked invites too)
   - add the source where the link was found, then press **Submit**
4. **View links.** Everything happens on the one links page (`/`), which shows a table with each server's icon, name, Discord description, member and online counts, source and submission time.
   - **Regular users** see only the links they submitted themselves, and can't change them. They don't see the Status column or the Status filter.
   - **Admins** see every link, plus the server ID, the status (Joined or Unjoined), the submitter's name and email, and an **Actions** column with three icon buttons:
     - **Joined/Unjoined** toggles whether the server has been joined (green when joined).
     - **Copy** copies the invite link to the clipboard.
     - **Delete** removes the link from the list. That server can't be submitted again.
     - **Restore** (shown on deleted links, next to Copy) puts a deleted link back in the list, unchanged and with its original submitter.
   - **Filters**, in any combination:
     - **Server name or description** (text search)
     - **Submitter** (admins only)
     - **Submitted from / to**: the date the link was submitted to this site (stored in the database), not when the Discord server was created. Both days are inclusive.
     - **Status** (admins only): All, Joined or Unjoined
     - **Deletion**: Not deleted (default), Deleted or All

These invite formats are accepted: `https://discord.gg/CODE`, `https://discord.com/invite/CODE`, `https://discordapp.com/invite/CODE`, or a bare `CODE`.

## API

All endpoints except register and login need an approved session. The `/api/admin` endpoints also need an admin account. Interactive docs are at `/docs` when `ENABLE_API_DOCS=true`.

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Apply for an account (`email`, `full_name`, `password`). The response is the same whether or not the email is already registered. |
| POST | `/api/auth/login` | Sign in. Pending or rejected users get `403`. |
| POST | `/api/auth/logout` | Sign out |
| GET | `/api/auth/me` | The current user |
| GET | `/api/admin/users?status=pending` | List users, optionally filtered by `pending`, `approved` or `rejected` |
| POST | `/api/admin/users/{id}/approve` | Approve a user |
| POST | `/api/admin/users/{id}/reject` | Reject a user, or revoke their access |
| GET | `/api/admin/submitters` | Users who have submitted at least one link, for the submitter filter |
| POST | `/api/admin/links/{id}/joined` | Mark a link's server as joined (`joined` becomes `true`) |
| DELETE | `/api/admin/links/{id}/joined` | Mark a link's server as not joined (`joined` becomes `false`) |
| DELETE | `/api/admin/links/{id}` | Delete a link. Its server stays blocked from being submitted again. |
| POST | `/api/admin/links/{id}/restore` | Restore a deleted link (`removed` becomes `false`). `404` if the link isn't deleted. |
| GET | `/api/links?q=&submitter_id=&date_from=&date_to=&joined=&deletion=` | List links. Regular users get only their own links, without submitter details; admins get every link with the submitting account (`register_account`). `q` matches the server name or description. `submitter_id` and `joined` are admin-only (`403` otherwise), and only admins get the `joined` field. `date_from`/`date_to` filter the submission time stored in the database (`register_time`), are ISO 8601, and are inclusive/exclusive. `joined` is `all` (default), `joined` or `unjoined`. `deletion` is `active` (default, not deleted), `deleted` or `all`. |
| POST | `/api/links/check` | Look up an invite on Discord and return the server's details and `already_registered` |
| POST | `/api/links` | Submit a link (`invite`, `source`). The invite must have been checked in this session within the last 30 minutes. Returns `409` if the server is already registered. |

## How it works

- **Discord lookup.** Uses Discord's public invite endpoint, `GET https://discord.com/api/v10/invites/{code}?with_counts=true`. No bot token is needed.
- **What's stored.** On submit, the invite is looked up on Discord again and the result is saved on the link: `guild_id`, `name`, `icon_url`, `description` (the server's own Discord description), `member_count`, `online_count`, `invite_url` and `expires_at`. The link also stores `source`, `joined` (false when submitted), `register_time`, `register_account` (the submitting user) and `removed`.
- **Duplicates.** Detected by `guild_id`, which has a unique constraint in the database. That constraint also catches two people submitting the same server at the same moment.
- **Deleting and restoring.** An admin's delete only hides the link: it sets `removed` and keeps the row. Because `guild_id` stays taken, that server can't be submitted again with any invite, and Check reports that it was removed by an administrator. Restore clears `removed`, so the same row is listed again with all its original data.
- **Check before submit.** A successful Check is recorded in the user's signed session cookie. A submission is refused unless its invite was checked by that session within the last 30 minutes. The invite is looked up on Discord again when it's submitted, so an invite that expired in between is caught.
- **Privacy.** The link list is scoped on the server: a regular user's request only ever returns links they submitted, and never includes submitter details. Check still reports when a server is already registered, without saying by whom.
- **Times.** Times are stored as `timestamp with time zone` and set by the database server's clock (`now()`), not the browser's. Database sessions run in UTC, and the API always sends times as UTC ISO 8601 ending in `Z`. The pages convert them to the viewer's own time zone, name that zone, and show the UTC time on hover. The **Submitted from / to** filters use the viewer's local calendar days.
- **Rate limits.** Failed sign-ins are limited to 10 per account and 30 per IP address per 15 minutes. After that, sign-in is refused with `429` and a `Retry-After` header, even with the right password, until the window passes. New applications are limited to 5 per IP per hour, and Check to 20 per user per minute, so one account can't get this server rate-limited by Discord. Limits are kept in memory per server process. Behind a reverse proxy, run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy IP>` so the limits see the visitor's IP address, not the proxy's.
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
  schemas.py       request and response models
  migrations.py    startup schema upgrades for existing databases
  security.py      bcrypt password hashing
  deps.py          current-user and admin dependencies
  discord.py       invite parsing and Discord lookup
  routers/
    auth.py        register, login, logout, me
    admin.py       user approval, link actions (joined, delete)
    links.py       check, submit, list (scoped per user)
    pages.py       HTML page routes
  templates/       Jinja2 HTML pages
  static/          CSS and JavaScript
tests/             pytest suite (fake Discord, separate test database)
```
