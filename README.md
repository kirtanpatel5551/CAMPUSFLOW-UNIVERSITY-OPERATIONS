# CampusFlow — University Operations Platform

A multi-module, runnable MS in Computer Science portfolio project. It includes student records, course catalog, sections, conflict-aware enrollment, waitlists, attendance, assessment scores, announcements, reporting, and an audit trail.

## Quick start (Windows)

1. Extract the ZIP and open PowerShell inside `campusflow-university-platform`.
2. Run `python app.py` (or `py app.py`).
3. Open http://127.0.0.1:8000.

Requires Python 3.10+. No `pip install`, Node, or database setup. A `campusflow.db` file is created on first run with sample university data.

If port 8000 is in use, stop the other server with Ctrl+C, or run `$env:CAMPUSFLOW_PORT="8001"; python app.py` and open http://127.0.0.1:8001.

## Modules

| Module | Working features |
| --- | --- |
| Overview | Enrollment, capacity, grade, and attendance metrics |
| Students | Student directory and create student |
| Courses | Catalog and create course |
| Sections | Term schedules, capacity, instructors, create section |
| Enrollment | Register, timetable conflict checks, waitlist, drop and automatic promotion |
| Attendance | Mark and update attendance for each enrolled student |
| Gradebook | Create weighted assessments, record scores, calculated course grade |
| Announcements | Publish messages to a section |
| Analytics | Course fill rates, grade averages, attendance rates, CSV export |
| Audit | Record key changes for review |

The platform simulates a university operations workflow. Concurrent enrollment is protected by a SQLite `BEGIN IMMEDIATE` transaction, and a student cannot hold overlapping sections in the same term. When a full section has a drop, the first eligible student on its waitlist is promoted; conflicts are skipped and remain waitlisted.

## Suggested demonstration

1. Open **Enrollment** and register a student in an available section.
2. Try registering the same student in a section at the same day and time; inspect the conflict message.
3. Fill a small section and register another student to create a waitlist entry.
4. Drop an enrolled student and watch the waitlist promotion.
5. Mark attendance, add an assessment, enter scores, and inspect Analytics.

## Data and API

SQLite tables: students, instructors, courses, sections, enrollments, attendance, assessments, scores, announcements, audit_log. The JSON API is implemented in `app.py`, with business rules in `services.py` and schema/sample data in `database.py`.

Examples: `GET /api/overview`, `GET /api/students`, `POST /api/enrollments`, `POST /api/attendance`, `GET /api/analytics`. Open the app's UI to explore all actions.

Run `python -m unittest discover -s tests -v` for enrollment, waitlist, conflict, and grade calculation tests.

## Production limitations and extensions

This is a **local educational demo**. It has no real authentication or authorization, and should not be made public or used with real student information. A deployable university system needs secure accounts and permissions, privacy controls, backup and migration processes, notification delivery, and a production database such as PostgreSQL.

For a deeper MS study, measure concurrent enrollment performance and waitlist fairness, then compare scheduling strategies or test PostgreSQL's transaction behavior under load.
