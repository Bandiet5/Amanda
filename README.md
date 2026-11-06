# Amanda se Kersfees

A complete, self-hosted, eight-person Christmas gift exchange. The participant journey starts with choosing a name, zooms into a wheel with 3D depth, and reveals 3D presents falling one after another, followed by the saved recipient’s name dropping last in gold 3D lettering onto the boxes. On desktop, the wheel and presents appear side by side with a short sparkle burst behind the wheel; on phones the recipient and gifts come first, with the wheel below. React + TypeScript + Vite, an SVG wheel, Flask, SQLite and Waitress. `/` is the participant experience; `/admin` is Amanda’s separate password-protected dashboard. The production frontend and API share one origin. No paid service, third-party login or cloud database is needed.

## Run locally

Requires Python 3.11+ and Node.js 24 LTS (Node is only needed to build the frontend). From the project root on Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm ci
flask --app server.wsgi:app db upgrade
npm run build
```

**The built-in admin password is `amanda123`**, as requested for this one-time event. It is seeded by the committed initial migration. You can optionally change it using `python -m server.cli set-admin-password`; that command requires at least 12 characters and signs out existing admin sessions. The repository includes a portable `.env` for immediate local testing. Optional machine-specific overrides can be generated with `python scripts/configure.py --development` in ignored `.env.local`; the script refuses to overwrite an existing file. Shell/PaaS environment values take precedence over both files.

Use two terminals, with the virtual environment active in the first:

```bash
flask --app server.wsgi:app run --host 127.0.0.1 --port 5000
```

```bash
npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api` to Flask. Use that exact origin (including `localhost`) for CSRF checks. Development HTTP is for this local workflow; production enforces HTTPS and secure cookies. The local Flask server is never the production server.

## Configure the event

1. Open `/admin` and sign in with `amanda123` (or your replacement password). Choosing the participant named Amanda does **not** authenticate an administrator.
2. In **Names for the Christmas wheel**, type all eight names and click **Save names**. Amanda can edit these names in the admin area at any time. The selector, wheel and presents update automatically within a few seconds. Exactly eight distinct names are required; renaming preserves browser links, recipient IDs and completed draws.
3. Share the participant URL. Each person chooses their own name, explicitly confirms “I am [name]”, then spins once. Claimed names remain visible and disabled.
4. Returning in the same browser restores the name and saved result, including after an interrupted animation. Result data is never stored in localStorage or sessionStorage.

**Browser binding is convenience protection for a trusted office event, not verified identity.** It cannot stop someone with a different browser from claiming an unclaimed name. Ask everyone to select only their own name. Clearing cookies, private browsing, a new browser profile or a changed phone needs Amanda’s recovery link. Anyone with an unused recovery link can redeem it, so share it privately.

Admin recovery controls:

- **Replay** asks the participant’s open page to animate the existing saved result again. It never changes assignments. The participant also has a replay button. An interrupted spin normally needs only a replay.
- **Recover** explicitly resets the old browser binding and returns a one-use link, valid for 24 hours. The name remains reserved and its saved result is retained. Open the link on the intended participant’s phone. Issuing another link replaces the previous one. Amanda can also create a recovery link for an unclaimed name; this reserves it and lets her correct a wrong-name selection on a revoked browser. The token travels in the URL fragment, is immediately removed from the address bar, and is stored only as a hash on the server.
- **New draw** uses a simple **Yes, give a new draw** confirmation button. It invalidates that participant’s old recipient, releases only their allocation, increments their draw version and preserves everyone else’s completed assignment. The same recipient can be selected again; with seven other completed draws it is necessarily the only valid option. Open pages reconcile every five seconds and when refocused. Before the final reveal, the client checks the saved state again.
- **Reveal recipients** requires a deliberate confirmation and records that access in the audit log. The normal dashboard response never contains assignments. Revealed assignments disappear when the event revision changes.
- **Reset entire event** uses a simple **Yes, reset everyone** confirmation button. It deletes current draws, clears claims, invalidates old participant sessions and recovery links, retains the eight names and administrative audit history, and creates a fresh round. Admin authentication remains separate.

The dashboard shows claim/draw timestamps, completion state and the latest 60 administrative audit entries. The database retains the full administrative log. All administrator actions use the one Amanda administrator account.

## Managed PaaS deployment (`wheelspin.infolab360.com`)

Keep the registered entry point **`server.wsgi:app`**. This app opts into the controller’s migration contract with committed `migrations/env.py`, `migrations/alembic.ini`, the `Flask-Migrate` dependency and revision `0001_gift_exchange`. App startup never creates tables or applies migrations.

The managed controller owns the order: clean fast-forward release → dependency installation → `flask --app server.wsgi:app db upgrade` under its app lock → Gunicorn activation/reload. Use its normal Update/Start/Reload actions. Do not add another systemd unit or an app startup migration wrapper. Managed previews deliberately do not apply migrations.

The checked-in `.env` is for local testing. Configure production values through the PaaS environment file outside the checkout so Git updates remain clean. For example, run as the PaaS service user (adjust `PAAS_DATA_ROOT` if yours differs):

```bash
.venv/bin/python scripts/configure.py --production \
  --origin https://wheelspin.infolab360.com \
  --database /srv/infolab/data/wheelspin/amanda.sqlite3 \
  --output /srv/infolab/data/wheelspin/app.env
```

This creates literal `NAME=value` entries compatible with PaaS, including `APP_ENV=production`, `PUBLIC_ORIGIN`, `SECRET_KEY`, `DATABASE_URL=sqlite:////srv/infolab/data/wheelspin/amanda.sqlite3` and `ALLOW_INSECURE_HTTP=0`. It does not overwrite an existing file. If an event database already exists, use its exact current path instead of the example.

Bind that file to the stopped app using the PaaS operator workflow, with required names `DATABASE_URL`, `SECRET_KEY`, `PUBLIC_ORIGIN`, `APP_ENV` and `ALLOW_INSECURE_HTTP`. Linux requirements include Gunicorn for the PaaS-managed process; Windows keeps Waitress. Build the frontend with `npm ci` and `npm run build` in the release checkout. Then let PaaS Start apply migrations and activate its existing Gunicorn process. `GET /api/health` returns 503 until the database is initialized, and 200 after the upgrade.

A first upgrade creates the schema and eight initial names. An existing database from release `25db2d3` is validated and adopted: its names, IDs, claims, assignments, timestamps, browser/recovery tokens, admin password and audit rows are retained. The same upgrade can be repeated safely. Partial or incompatible legacy schemas fail without changing event data; fix the migration in Git and retry through PaaS. The initial baseline deliberately rejects downgrading below it because that would remove event data. Future revisions can still downgrade back to the baseline.

`DATABASE_URL` controls both the migration engine and runtime SQLite connection. `DATABASE_PATH` is retained for older installations when no URL is set. SQLite stays the runtime database; PostgreSQL is used only by a separate migration portability test. No Postgres service is needed to host this application.

For standalone development/office installs, apply the same committed upgrade explicitly before starting the web server:

```bash
.venv/bin/flask --app server.wsgi:app db upgrade
```

`python -m server.cli init-db` remains a compatibility alias for that migration command; it no longer creates a separate schema.

## Office-server deployment (Linux)

Use a persistent local disk for SQLite, **not a network share**. The following assumes a Debian/Ubuntu-style server, Node 24 already installed, and Caddy installed using its [official installation instructions](https://caddyserver.com/docs/install). Replace `gifts.your-company.co.za` with your actual hostname. These commands create a dedicated service account and install from this checkout:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv rsync
sudo useradd --system --home /opt/amanda --shell /usr/sbin/nologin amanda
sudo mkdir -p /opt/amanda /var/lib/amanda
sudo rsync -a --exclude=.venv --exclude=node_modules --exclude=.env --exclude=instance --exclude=dist --exclude=artifacts --exclude=test-results ./ /opt/amanda/
sudo chown -R amanda:amanda /opt/amanda /var/lib/amanda
sudo chmod 700 /var/lib/amanda
sudo -u amanda python3 -m venv /opt/amanda/.venv
sudo -u amanda /opt/amanda/.venv/bin/python -m pip install -r /opt/amanda/requirements.txt
cd /opt/amanda
sudo -u amanda npm ci
sudo -u amanda npm run build
sudo -u amanda .venv/bin/python scripts/configure.py --production --origin https://gifts.your-company.co.za --database /var/lib/amanda/amanda.sqlite3
sudo -u amanda .venv/bin/flask --app server.wsgi:app db upgrade
sudo cp deploy/amanda.service /etc/systemd/system/amanda.service
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudoedit /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl enable --now amanda
sudo systemctl reload caddy
```

If the `amanda` account already exists, skip `useradd`. The configuration command intentionally refuses to replace `.env.local`; keep that local override when upgrading an existing installation. The example Caddyfile is for a dedicated Caddy instance; add its site block to the existing configuration if the server hosts other sites. If Node is installed only in a personal version manager, make the Node 24 executable available to the service account for the build.

Waitress binds only to `127.0.0.1:8080`; Caddy serves HTTPS and proxies both UI and API to it. It passes proxy headers that Waitress trusts **only from loopback**. The systemd service runs without debug mode, restarts after a failure and permits writes only to `/var/lib/amanda`. The database, `.env` and backups are never served as static files.

For a publicly trusted certificate, point the real hostname’s DNS to the server and arrange the appropriate port 80/443 access with IT. Caddy manages certificate issuance and renewal. For an internal-only site without a public domain, use `deploy/Caddyfile.internal`, set the matching `PUBLIC_ORIGIN`, configure office DNS, and have IT install Caddy’s root CA certificate on every phone. A private CA requires explicit device trust; see [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).

**Phones need network access to the server**: usually the same office Wi-Fi, with client isolation disabled as appropriate, or a properly configured external address/VPN. `localhost` on a phone refers to the phone itself. Share `https://your-configured-hostname/`, allow HTTPS through the server firewall, and keep port 8080 private. Test that URL on an actual office phone before the event.

Useful operator commands:

```bash
sudo systemctl status amanda
sudo journalctl -u amanda -n 100 --no-pager
curl --fail https://gifts.your-company.co.za/api/health
sudo systemctl restart amanda
```

## Windows office server

Waitress also runs on Windows. In PowerShell from the project directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
npm run build
.\.venv\Scripts\python.exe scripts/configure.py --production --origin https://gifts.your-company.co.za --database C:/ProgramData/Amanda/amanda.sqlite3
.\.venv\Scripts\python.exe -m server.cli init-db
.\.venv\Scripts\waitress-serve.exe --listen=127.0.0.1:8080 --threads=8 --trusted-proxy=127.0.0.1 --trusted-proxy-headers="x-forwarded-for x-forwarded-proto x-forwarded-host" server.wsgi:app
```

Run Caddy in a second terminal with `caddy run --config deploy/Caddyfile` after changing its hostname. The same DNS, HTTPS and phone-access requirements apply. Use Task Scheduler at startup with “Run whether user is logged on or not” and automatic restart, or your organisation’s service wrapper, to keep Waitress and Caddy running under a restricted account. Set the task’s working directory to this project. Give that account write access to `C:\ProgramData\Amanda`, protect local configuration with Windows ACLs, and deny other users access to the database, backups and environment secrets. No Unix-specific WSGI server is required.

## Configuration and persistence

The checked-in `.env` provides local defaults. `.env.local` is an optional ignored override, and actual process environment variables win over both. See `.env.example` for production settings. `scripts/configure.py` creates `.env.local` by default, or a PaaS environment file at an explicit `--output` path:

| Variable | Meaning |
| --- | --- |
| `APP_ENV` | `production` (default) or `development` for local work |
| `SECRET_KEY` | At least 32 random characters; generated by the setup script; never put it in frontend code |
| `PUBLIC_ORIGIN` | Exact origin, e.g. `https://gifts.your-company.co.za`, without a path; also used for CSRF checks, trusted host validation and recovery links |
| `DATABASE_URL` | PaaS migration/runtime contract, e.g. `sqlite:////srv/infolab/data/wheelspin/amanda.sqlite3`; relative local URLs resolve from the process working directory |
| `DATABASE_PATH` | Backward-compatible SQLite path when `DATABASE_URL` is not set; do not point the two settings at different files |
| `ALLOW_INSECURE_HTTP` | `0` in production; `1` only for local development |
| `ADMIN_PASSWORD_HASH` | Optional precomputed Werkzeug scrypt hash; overrides the database password. The interactive command is preferable. No plaintext password environment variable is used. |

Secure, HttpOnly participant cookies last 180 days; separate administrator sessions expire after 12 hours and use a Strict SameSite cookie. Only SHA-256 token hashes are stored server-side; CSRF tokens are HMAC-bound to the relevant session. Login limits are persisted in SQLite (five failures per address and 30 globally per 15-minute window), so restarting the server does not reset them. Cookie-authenticated writes require a session-specific CSRF header and reject a mismatched Origin. Responses containing session state/results are marked `no-store`.

Keep `SECRET_KEY` stable across restarts. Rotating it changes CSRF tokens; participants must reload, but their saved draws remain bound to their existing opaque browser token. To recover the admin password, run `set-admin-password` again on the server. If `ADMIN_PASSWORD_HASH` is set, unset it before using that command; changing an environment-supplied hash requires a restart and does not by itself revoke already-issued sessions. The interactive command does revoke them.

For a live, consistent backup (including data in SQLite’s WAL):

```bash
cd /opt/amanda
sudo -u amanda .venv/bin/python -m server.cli backup /var/lib/amanda/backup-before-event.sqlite3
```

Use a new filename each time; the command refuses to overwrite an existing file or write into public directories. Keep backups private. To restore: stop the service; move the current database **and its `-wal` and `-shm` companions** into a private quarantine folder; copy the backup to the file selected by `DATABASE_URL` (or `DATABASE_PATH` on older installs), restore its owner and restrictive permissions, and restart the service. Never replace a live SQLite file. Restoring a backup also restores its event, session and recovery state; retire recovery links issued after that backup and reconcile any draws made since it was taken with Amanda. Build/deploy updates must preserve the database and the machine/PaaS environment overrides.

## How a draw stays correct

`BEGIN IMMEDIATE` serialises claim/draw/reset writes, with a 15-second busy timeout and SQLite WAL. A draw loads all remaining givers and available recipients, removes self-edges, and tests every possible candidate with an exact augmenting-path matching. `secrets.choice` selects only among candidates that still admit a complete assignment. Giver/recipient uniqueness, event-bound foreign keys and the self-draw check are also enforced by SQLite constraints. Repeated draw requests return the original stored allocation and exact segment list.

The client immediately locks the spin button, renders that committed segment list, rotates six full turns to the saved recipient’s centre, then verifies the current saved state before showing it. Timeouts trigger a state recovery rather than a second blind spin. Refreshing mid-animation restores the committed result. Draw versions reject stale participant requests and prevent an old admin confirmation from resetting a newly completed replacement draw. Reduced-motion mode uses a 350 ms reveal, and no sound is needed or played. See [SQLite transaction locking](https://www.sqlite.org/lang_transaction.html) and [Flask’s production guidance](https://flask.palletsprojects.com/en/stable/deploying/).

## Verification

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
npm test
npm run build
npm run test:browser
```

All fixtures and the browser server explicitly apply the committed migrations. Browser tests use a disposable database and an isolated Waitress server on port 5055; they never touch the real event. They use installed Google Chrome when available. Otherwise run `npx playwright install chromium` once, or set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to your Chrome/Chromium executable.

- **63 SQLite/backend tests** cover 24 draw orders, all eight participants completing, concurrent claims, 16 simultaneous draw requests, SQL constraints, idempotent retries, discarded responses, server restarts, identity/CSRF protection, independent admin authentication, recovery expiry/reuse, replay, admin-only name editing with preserved allocations, stale-tab conflicts, both reset types, fail-closed production configuration, private secret setup, password changes, consistent live backups, fresh/legacy migration paths, transactional failure preservation, metadata consistency and the exact PaaS CLI entry point. Matching is compared with an independent exhaustive oracle across all **12,870** equal-sized giver/recipient subset pairs.
- **9 frontend tests** check actual pointer mathematics for every winning segment from multiple existing rotations, including a single recipient and reduced motion.
- **12 Chrome browser tests** cover desktop (1440 px) and mobile (360 px), no horizontal overflow, the live committed-result animation, refresh mid-spin, loss of the draw response, session restoration, reduced motion, admin reveal and new draw, one-use recovery through the real interface, the final single-recipient reveal, cancellation of a stale in-flight reveal, name editing, button-based full-event confirmation, and WCAG A/AA accessibility scans of the participant and admin screens. Screenshots are written to ignored `artifacts/`.

The suite runs against the built same-origin production frontend. Viewport emulation is not a physical-phone/network/TLS deployment test. Configure the office hostname, persistent database location and HTTPS/device trust on the actual server before sharing it.

## Assets

Festive decorations, gift illustrations and the wheel are original SVG/CSS in this project. Fonts are locally bundled via Fontsource (Cormorant Garamond and DM Sans, SIL Open Font License); Lucide icons use the ISC license. See `THIRD_PARTY_NOTICES.md`. No external runtime font, image, API or authentication service is required.

## Pull onto your server

Once the GitHub repository is available, clone it on the server:

```bash
git clone https://github.com/Bandiet5/Amanda.git
cd Amanda
```

For later updates, run these from the installed checkout, using the service account if the files belong to it:

```bash
git pull --ff-only
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/flask --app server.wsgi:app db upgrade
npm ci
npm run build
sudo systemctl restart amanda
```

Use the office-server setup above for the first deployment. The repository includes `.env` local defaults as requested. Machine overrides in `.env.local`, the event database, browser claims, saved draws and backups remain outside Git. Amanda enters the actual participant names in `/admin` on the server; they are saved to that server’s persistent database.

The PostgreSQL portability check is separate from the SQLite runtime. On a development machine with PostgreSQL 16 tooling:

```bash
pg_virtualenv -t -v 16 .venv/bin/python tests/run_postgres_migrations.py
```

It creates a throw-away cluster and tests real foreign keys, uniqueness, self-draw rejection, seeds and repeated upgrades. Without that test environment, the PostgreSQL test is reported as skipped by the normal pytest run. The normal suite requires no PostgreSQL server.
