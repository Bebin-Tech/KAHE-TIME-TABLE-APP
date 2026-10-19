# Implementation plan

1. Foundation: custom user, session authentication, role checks, MySQL configuration, React shell, migrations and authentication tests.
2. Academic modules: normalized academic hierarchy, scoped CRUD, faculty/student profiles, rooms and institutional configuration.
3. Scheduling: versioned timetable, transactional validation, revision checks, React drag-and-drop editor and undo/redo.
4. Workflow: review transitions, publication, immutable history, notifications.
5. Dashboards: role-specific live schedules and summaries.
6. Reports: authorized PDF/XLSX exports and utilization/hour reports.
7. QA: business-rule tests, MySQL concurrency checks, responsive verification, deployment documentation.

Do not label later phases complete before checks pass. MySQL availability is a separate acceptance gate even if SQLite tests pass.
