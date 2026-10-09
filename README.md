College Tutorial Management System (CTMS)

A simple Django web app for managing online tutorials, attendance, student
feedback, complaints, and lecturer claims — built to the "simple over
clever" principle: server-rendered pages, one relational database, no
Microsoft Teams API integration (just a stored meeting link), and a small
rule-based sentiment classifier instead of a heavy ML pipeline.

 explanation by papakwame, developer

- **Three roles**: Administrator, Lecturer, Student — each gets their own
  dashboard and is restricted server-side (not just hidden buttons) to
  their own data.
- **Tutorial monitoring**: course/tutorial scheduling, "Join Tutorial" /
  "Start Tutorial" attendance capture, student feedback with automatic
  sentiment tagging, and student complaints with admin resolution.
- **Claims**: lecturers see only tutorials that are actually eligible
  (lecturer attendance + student attendance + feedback + not already
  claimed), submit a claim, and admins approve/reject with a required
  rejection reason.
- **AI-assisted appraisal**: a simple keyword-based sentiment classifier
  (positive/neutral/negative) plus an aggregated, factual summary — no
  external API key required, and it never overwrites the original comment.
- **Admin data management** (students, lecturers, courses, enrollments,
  tutorials) is handled through Django's built-in admin site at `/admin/`
  rather than reinventing CRUD screens — the custom pages are reserved for
  the workflow-specific screens (claims review, monitoring, appraisal,
  reports).

 Project layout

```
ctms/
├── manage.py
├── requirements.txt
├── ctms/                # project settings & URLs
└── core/                # the whole application
    ├── models.py         # all 12 entities from the spec
    ├── views.py           # student / lecturer / admin views
    ├── forms.py
    ├── decorators.py      # server-side role_required() check
    ├── sentiment.py        # simple keyword-based sentiment analysis
    ├── admin.py            # Django admin registrations
    ├── urls.py
    ├── templates/core/     # all page templates (Bootstrap via CDN)
    └── management/commands/seed_data.py   # demo data
```

Running it locally

```bash
cd ctms
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data        # creates demo admin/lecturers/students/tutorials
python manage.py runserver
```

Then open http://127.0.0.1:8000/ — you'll be redirected to the login page.

 Demo accounts (development only — do not use these in production)

| Role      | Username     | Password     |
|-----------|--------------|--------------|
| Admin     | `admin`      | `admin12345` |
| Lecturer  | `john.doe`   | `lecturer123`|
| Lecturer  | `jane.smith` | `lecturer123`|
| Student   | `student1`   | `student123` |
| Student   | `student2`…`student6` | `student123` |

The admin account also has access to Django's built-in admin site at
`/admin/` for managing users, courses, and tutorials directly.

 Walking through the core workflow

1. Log in as `admin`, go to **Manage Data** (`/admin/`) to see/add
   students, lecturers, courses, enrollments, and tutorials — the demo
   data already has examples of each tutorial state (upcoming, active,
   completed, cancelled).
2. Log in as `student1`, open **My Timetable**, click **Join** on a
   tutorial (this records attendance and opens the Teams link), then
   leave **Feedback**.
3. Log in as `john.doe` (the lecturer for that tutorial), open
   **My Timetable**, click **Start Tutorial** to record lecturer
   attendance.
4. Still as the lecturer, open **Submit Claim** — the tutorial is now
   eligible (lecturer attendance + student attendance + feedback) —
   select it and submit.
5. Log back in as `admin`, go to **Claims**, open the new claim, and
   **Approve** or **Reject** (a rejection requires a reason).
6. The lecturer can see the claim's status and, if rejected, the reason
   under **My Claims**.
 
 
Secrets (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`) are
read from environment variables with safe local-dev defaults — set real
values before deploying anywhere public.
