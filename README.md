# CTMS — College Tutorial Management System

A Django web application for running online tutorials end to end: scheduling,
attendance, student feedback, complaints and lecturer claims.

It is built to a **simple over clever** principle — server-rendered pages, one
relational database, a stored meeting link instead of a Microsoft Teams
integration, and a small rule-based sentiment classifier instead of an ML
pipeline.

> This is the original server-rendered implementation. The same domain was later
> rebuilt as a JSON API in [**ug-ctms**](https://github.com/pkaycodes/ug-ctms)
> (Express, PostgreSQL, JWT) — useful as a comparison between a monolithic
> Django design and a split client/server one.

## What it does

### Three roles, enforced server-side

Administrators, lecturers and students each get their own dashboard. Access is
checked with a `role_required()` decorator on every view, so a student cannot
reach a lecturer page by typing the URL — the restriction is not just hidden
buttons.

### Tutorial monitoring

Courses and tutorials are scheduled, then attendance is captured from both
sides: students click **Join Tutorial**, lecturers click **Start Tutorial**.
Students leave feedback afterwards, which is tagged automatically as positive,
neutral or negative. Students can also raise complaints, which administrators
resolve.

### Claims

Lecturers see only the tutorials that are genuinely claimable, submit a claim
for one or more of them, and administrators approve or reject it. A rejection
requires a written reason, and the lecturer sees that reason under **My Claims**.

A tutorial is eligible only when all of the following hold:

- the lecturer recorded attendance;
- at least one student recorded attendance;
- at least one feedback entry exists;
- the tutorial was not cancelled;
- it is not already part of a pending or approved claim.

The check is done in the query that builds the eligible list, so an ineligible
tutorial cannot be submitted by crafting a request.

### Appraisal

Each feedback entry gets a sentiment tag and the appraisal page presents an
aggregated, factual summary. The original comment is stored and displayed
verbatim — the classifier never rewrites what a student wrote. No external API
key is involved.

### Data management

Students, lecturers, courses, enrolments and tutorials are managed through
Django's built-in admin at `/admin/`. The custom screens are reserved for the
workflow-specific views (claims review, monitoring, appraisal, reports) rather
than reimplementing CRUD.

## Data model

Twelve entities, all in `core/models.py`:

`User` · `Student` · `Lecturer` · `Course` · `CourseEnrollment` · `Tutorial` ·
`StudentAttendance` · `LecturerAttendance` · `Feedback` · `Complaint` · `Claim` ·
`ClaimItem`

`ClaimItem` is the join between a claim and the tutorials it covers, which is
what lets one claim bundle several sessions while the eligibility rule stays
enforceable per tutorial.

## Project layout

```
ctms/
├── manage.py
├── requirements.txt
├── ctms/                  # project settings & URLs
└── core/                  # the whole application
    ├── models.py          # the 12 entities
    ├── views.py           # student / lecturer / admin views
    ├── forms.py
    ├── decorators.py      # server-side role_required() check
    ├── sentiment.py       # keyword-based sentiment analysis
    ├── admin.py           # Django admin registrations
    ├── urls.py
    ├── templates/core/    # page templates (Bootstrap via CDN)
    └── management/commands/seed_data.py
```

## Running it locally

Requires Python 3.12+ (Django 6 requires it).

```bash
cd ctms
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data      # demo admin, lecturers, students and tutorials
python manage.py runserver
```

Then open <http://127.0.0.1:8000/> — you will be redirected to the login page.

`seed_data` creates tutorials in every state (upcoming, active, completed,
cancelled), including two that are already eligible for a claim.

### Demo accounts

Development only — do not use these in production.

| Role | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `admin12345` |
| Lecturer | `john.doe` | `lecturer123` |
| Lecturer | `jane.smith` | `lecturer123` |
| Student | `student1` … `student6` | `student123` |

The administrator also has access to Django's built-in admin at `/admin/`.

## Walking through the workflow

1. Log in as `admin` and open **Manage Data** (`/admin/`) to see students,
   lecturers, courses, enrolments and tutorials.
2. Log in as `student1`, open **My Timetable**, click **Join** on a tutorial
   (this records attendance and opens the meeting link), then leave
   **Feedback**.
3. Log in as `john.doe`, the lecturer for that tutorial, open **My Timetable**
   and click **Start Tutorial** to record lecturer attendance.
4. Still as the lecturer, open **Submit Claim** — the tutorial is now eligible
   — select it and submit.
5. Log back in as `admin`, open **Claims**, and approve or reject the claim. A
   rejection requires a reason.
6. As the lecturer, the claim's status and any rejection reason appear under
   **My Claims**.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Signing key | development placeholder |
| `DJANGO_DEBUG` | Debug mode | `True` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1,testserver` |

Set real values before exposing the app anywhere public, and in particular set
`DJANGO_DEBUG=False` and a strong `DJANGO_SECRET_KEY`.

## Licence

MIT — see [LICENSE](LICENSE).
