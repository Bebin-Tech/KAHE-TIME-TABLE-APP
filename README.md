# College Timetable Management System

Django 5.2 LTS, React 19, TypeScript, dnd-kit, MySQL 8.x. Django serves the compiled React application on the same origin; authentication uses Django sessions and CSRF. Accounts are institution-created; there is no public signup.

**Acceptance status:** the application is implemented and tested locally with SQLite. MySQL connection, migrations and real row-lock concurrency verification are pending local server configuration. See `PROJECT_STATUS.md` for the exact verified scope and outstanding work. Do not deploy this as a verified production system yet.

## Windows prerequisites

- Python 3.12 (the session found bundled Python **3.12.14**; Windows `py`/`python` Store aliases were unusable).
- Node.js 22.12+ or 24; Node **24.15.0** and npm **11.12.1** were detected.
- MySQL Server 8.x, running and accepting connections. MySQL 8.0 was installed but was not listening on 127.0.0.1:3306 during initial inspection.
- VS Code and PowerShell. Keep this project outside a synced folder in production.

Open PowerShell in this project directory. With a normal Python installation:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For the exact runtime found on this computer (also works around bundled `ensurepip` failure):

```powershell
$CtmsPython = 'C:\Users\bbebi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $CtmsPython -m venv --without-pip .venv
& $CtmsPython -m pip --python .venv\Scripts\python.exe install pip
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If activation is blocked, call `.\.venv\Scripts\python.exe` directly instead of changing machine-wide execution policy.

## MySQL database

Start the configured MySQL service using Windows Services. Use MySQL's administrator account interactively; do not put its password in command-line arguments:

```powershell
& 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe' -u root -p
```

Run the following SQL, replacing the example password with a strong local secret:

```sql
CREATE DATABASE ctms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'ctms_app'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_A_STRONG_LOCAL_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES
ON ctms.* TO 'ctms_app'@'127.0.0.1';
```

These schema privileges are needed for migrations. In production, separate the migration principal from the runtime principal; runtime normally needs SELECT/INSERT/UPDATE/DELETE only. Do not grant global privileges to the application.

```powershell
Copy-Item .env.example .env
code .env
```

Set `DB_ENGINE=mysql`, the database/user above, and `DB_PASSWORD`. Keep `.env` private; it is ignored by Git. Generate a secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Put that output in `DJANGO_SECRET_KEY`. Use `DJANGO_DEBUG=true` only for local development. Database settings are read by `config/settings.py`; the MySQL connection uses utf8mb4 and strict SQL mode. Times are stored in UTC; scheduling clock times are interpreted in the institution timezone.

## Build, migrate and run

```powershell
npm ci --prefix frontend
npm run build --prefix frontend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_academics  # optional configurable examples; creates no login credentials
python manage.py runserver 127.0.0.1:8000 --noreload
```

Visit [the local app](http://127.0.0.1:8000/). New superusers default to the Admin role and have institution-wide access. Use the React Users screen to create other accounts, assign roles and deactivate accounts. User deletion is deliberately disabled to preserve audit history.

Schema changes are committed as migrations. After changing models during development, run `python manage.py makemigrations`, review the generated migration, then `python manage.py migrate`.

For frontend changes, rebuild before refreshing Django. A second terminal can run:

```powershell
npm run build --prefix frontend -- --watch
```

To run separate Django and Vite development servers in PowerShell:

```powershell
pwsh -NoProfile -File .\scripts\run-backend.ps1
# In a second terminal:
pwsh -NoProfile -File .\scripts\run-frontend.ps1
```

The frontend runs at http://127.0.0.1:5173 and forwards `/api` and `/accounts` to Django at http://127.0.0.1:8000. Production builds retain the `/static/` asset base. Without `.env`, the backend script clearly announces a temporary SQLite development fallback. With `.env`, it uses the configured database. VS Code's **Tasks: Run Task → CTMS: Start frontend and backend** provides the same commands in grouped integrated terminals. Stop any existing servers before starting these tasks to avoid port conflicts.

For an explicit SQLite-only local check, temporarily set `$env:DB_ENGINE='sqlite'` and `$env:DJANGO_DEBUG='true'` in that PowerShell session. It uses ignored `development.sqlite3`. This is an alternative for local development, **not MySQL verification**. Remove the override with `Remove-Item Env:DB_ENGINE` before testing `.env` MySQL settings. Environment variables override `.env`.

## First configuration

1. Configure Institution Settings: name, IANA timezone, working weekdays as JSON (`[0,1,2,3,4]`, Monday=0), approval and weekly-hour policy.
2. Add departments, programs, academic years, semesters and sections. Semesters and sections are configurable; odd/even semesters follow their number.
3. Create users, faculty and student profiles. Assign HOD department access explicitly. `can_publish` is separate and false by default.
4. Add rooms/labs, equipment as JSON lists, teaching periods and breaks. Periods need valid start/end times. Consecutive sessions require contiguous periods and cannot span breaks or gaps.
5. Add subjects with semester, required weekly periods, session duration, room type and equipment; add eligible faculty/subject/year assignments.
6. Configure faculty and room availability and approved leave. Unavailable intervals exclude those times; when available windows exist for a weekday, the full class must fit in one. Unspecified weekdays are available unless otherwise restricted.
   Department Rules supports per-section daily period limits and daily subject limits, with hard-conflict or warning policy. Zero disables a limit.
7. Create a section draft, drag a teaching assignment to a slot, choose a room, validate the change, and Save Draft. The Add button offers a keyboard-accessible alternative. Changes are held in memory until saved, with undo/redo and navigation warnings.
8. Validate the full week and submit. An Admin approves or returns it with a reason. Admin or a department-authorized publisher publishes. When approval is disabled, an authorized publisher may publish a draft directly.
9. Create a revision to alter an official version. The existing published version remains visible until its replacement is published atomically.

Faculty and students receive only authorized published schedules. Faculty can submit leave, unavailable-interval or scheduling-conflict requests. Admin/HOD reviews are department scoped. Approving leave or unavailable intervals cannot invalidate a published schedule; revise or withdraw affected schedules first.

## Scheduling and concurrency

### Optional full sample dataset

`python manage.py seed_demo_data --admin admin` adds a labeled `DEMO-CS` department with `DEMO-BCA`, five subjects, four faculty accounts plus an HOD, twelve students, two classrooms and a shared computer lab. It requires DEBUG true and an existing active administrator. The command prints a randomly generated temporary password for newly created sample accounts; it never resets existing passwords or changes the administrator password.

- `demo.hod`: department HOD; publication remains Admin-only by default.
- `demo.faculty01` through `demo.faculty04`: Python, mathematics, web technology and lab faculty.
- `demo.student01` through `demo.student06`: section A, with a published schedule.
- `demo.student07` through `demo.student12`: section B, whose sample timetable awaits approval/publication.

In Timetables, filter `DEMO-BCA`. Section A has an archived version, a published version and an editable draft. The draft intentionally leaves Communication English empty on Friday's third teaching period: drag that assignment into the empty slot, choose `DEMO-A101`, save, validate and submit. Section B is submitted and ready for Admin approval and publication. The full published/submitted weeks each contain 25 teaching periods, including three two-period laboratory sessions. The sample also contains a pending faculty request, availability, approved weekend leave, notifications and real workflow/audit history.

Rerunning this command avoids duplicate records and preserves existing sample edits. All changes use real database records and the same scheduling/workflow services as the UI. Accounts, schedules and rooms are fictional development examples.

`timetables/services.py` owns draft creation, full-snapshot saves and workflow changes. All scheduling and master-data mutations serialize using a singleton `SELECT ... FOR UPDATE` lock and transactions on MySQL. Revision tokens reject stale saves with HTTP 409; draft-creation UUIDs make retries idempotent. Every save revalidates the entire proposed schedule. No official version is edited in place.

Validation compares actual intervals, including across departments and overlapping academic-year date ranges. It checks section/faculty/room bookings, faculty eligibility, availability/leave, room capacity/type/equipment, breaks, contiguous blocks, weekly requirements and workload. Incomplete weekly requirements are warnings during draft editing and block complete validation/publication when configured. Excess weekly periods and other hard conflicts block saves. Other live section drafts reserve resources conservatively; revisions of the same section are treated as alternatives. SQLite does not provide the same row-lock guarantee.

Recurring weekly classes currently apply throughout the academic year. Approved leave on any occurrence of that weekday blocks the recurring assignment. Date-specific replacement lessons and rotating-week calendars require further implementation.

## Reports and exports

Reports displays published faculty workload, room period utilization and subject-hour completion within the current user's access. Timetables supports daily filtering and browser print/save-PDF. Reports exports real PDF and XLSX files. Authorized filters may also be used:

```text
/api/exports/pdf/?timetable=123
/api/exports/pdf/?department=1
/api/exports/pdf/?faculty=2
/api/exports/xlsx/?timetable=123
```

Filters narrow the server-authorized dataset. They never expand access. Faculty exports contain personal lessons only; students see their assigned section only. PDF exports use a paginated tabular layout; the browser print view preserves the weekly grid.

## Tests

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 2
npm run build --prefix frontend
```

Django creates a dedicated test database; never point testing at production. For MySQL testing, use a **separate test principal**, grant privileges only on `test_ctms.*`, and use a separate environment/session. Django's default test name is `test_` plus `DB_NAME`; it needs CREATE/DROP on that test database. The MySQL-only threaded test checks that two parallel section saves cannot reserve the same faculty and room. It is explicitly skipped on SQLite.

Backend test files cover authentication, inactive accounts, CSRF, role checks, CRUD, relationship scoping, request reviews, scheduling conflicts, rollback, stale edits, practical sessions, workflow, notifications, revisions, export file signatures and access. Browser smoke verification used local SQLite and an isolated review account. Full browser automation and load/security reviews remain outstanding in `PROJECT_STATUS.md`.

## Email

The default console backend prints password-reset links to the server terminal for local development. Configure `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` and the SMTP fields in `.env` for delivery. Test actual delivery before deployment. No reset email is sent to nonexistent/inactive accounts.

## Troubleshooting

- **Python opens Microsoft Store / cannot be accessed:** install Python 3.12 from python.org or use the detected bundled runtime above. Avoid relying on broken Store aliases.
- **ensurepip failed:** use the base runtime's `pip --python` bootstrap above.
- **MySQL 2003 / connection refused:** start the service, confirm its configured port, and check `Test-NetConnection 127.0.0.1 -Port 3306`.
- **Access denied 1045:** check MySQL username, password and host-specific grants. The examples use 127.0.0.1 consistently.
- **mysqlclient wheel unavailable:** use 64-bit Python 3.12 with a current pip; building from source needs the MySQL client development libraries and Visual C++ build tools.
- **Blank/unstyled app:** run the frontend build, then restart Django so static asset discovery includes `frontend/dist`. Inspect `/static/assets/main.js` and `/static/assets/style.css`.
- **CSRF 403:** open the app through Django on one consistent host; enable cookies. Use HTTP only with DEBUG true locally; production requires HTTPS.
- **HTTP redirects to HTTPS locally:** `.env` has DEBUG false. Set it true only in local development.
- **Port 8000 unavailable:** try `python -u manage.py runserver 127.0.0.1:8001 --noreload --nothreading`. This command reached a listening server during verification.
- **409 stale revision:** reload the latest saved version. Unsaved changes are not silently overwritten.
- **422 conflict:** read the conflict message and corrective action; the server preserves the previous persisted schedule.
- **Leave approval blocked:** withdraw or revise the published lessons that would overlap the leave before approving.

## Production checklist and backup

- Complete MySQL integration/concurrency tests and the remaining acceptance items first.
- Set DEBUG false, a unique secret, exact ALLOWED_HOSTS, HTTPS, secure cookies and HSTS. Configure trusted CSRF origins if a reverse proxy requires them. Configure the proxy's HTTPS forwarding correctly; do not trust arbitrary forwarded headers.
- Use a supported WSGI/ASGI server behind a reverse proxy, never Django runserver. On Windows a separately installed Waitress is an option; Linux deployments commonly use Gunicorn/Uvicorn. These deployment servers are not installed or verified by this session.
- Run `python manage.py check --deploy`, migrations, and `python manage.py collectstatic --noinput`; serve STATIC_ROOT through the proxy. Build frontend assets before collectstatic.
- Separate migration/runtime database principals, use MySQL InnoDB, restrict network access and back up secrets outside Git.
- Configure SMTP, log retention/access controls, monitoring, login throttling at the proxy, dependency updates and restore drills. Protect audit logs from ordinary database users and restrict direct database changes.
- Take encrypted backups before migrations and daily thereafter. Example interactive backup command (PowerShell-safe output handling through MySQL's own option):

```powershell
& 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe' -u ctms_backup -p --single-transaction --no-tablespaces --result-file='C:\SecureBackups\ctms.sql' ctms
```

Create and grant a dedicated backup user according to your DBA policy; `ctms_backup` is an example, not a seeded account. Keep backup files outside the served project, encrypt them, restrict file ACLs, rotate them, and test restoring into a separate database. Record recovery point/time targets before production use.
