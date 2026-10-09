from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .decorators import role_required
from .forms import LoginForm, FeedbackForm, ComplaintForm, ClaimRejectForm
from .models import (
    User, Student, Lecturer, Course, CourseEnrollment, Tutorial,
    StudentAttendance, LecturerAttendance, Feedback, Complaint, Claim, ClaimItem,
)
from .sentiment import analyze_sentiment, summarize_feedback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sync_tutorial_status(tutorial):
    """Recompute Upcoming/Active/Completed from the clock (spec section 19).

    Cancelled tutorials are left untouched — only an administrator sets that.
    """
    if tutorial.status == Tutorial.Status.CANCELLED:
        return tutorial

    now = timezone.localtime()
    naive_start = timezone.datetime.combine(tutorial.date, tutorial.start_time)
    naive_end = timezone.datetime.combine(tutorial.date, tutorial.end_time)
    start = timezone.make_aware(naive_start) if timezone.is_naive(naive_start) else naive_start
    end = timezone.make_aware(naive_end) if timezone.is_naive(naive_end) else naive_end

    if now < start:
        new_status = Tutorial.Status.UPCOMING
    elif start <= now <= end:
        new_status = Tutorial.Status.ACTIVE
    else:
        new_status = Tutorial.Status.COMPLETED

    if new_status != tutorial.status:
        tutorial.status = new_status
        tutorial.save(update_fields=["status"])
    return tutorial


def sync_many(tutorials):
    for t in tutorials:
        sync_tutorial_status(t)
    return tutorials


def is_claim_eligible(tutorial):
    """Rule 7 (spec section 54): the basic claim-eligibility check."""
    if tutorial.is_cancelled():
        return False, "Tutorial is cancelled."
    if not hasattr(tutorial, "lecturer_attendance"):
        return False, "Lecturer attendance was not recorded."
    if not tutorial.student_attendances.exists():
        return False, "No student attendance was recorded."
    if not tutorial.feedback_entries.exists():
        return False, "No student feedback has been submitted."
    already_claimed = ClaimItem.objects.filter(
        tutorial=tutorial, claim__status__in=[Claim.Status.PENDING, Claim.Status.APPROVED]
    ).exists()
    if already_claimed:
        return False, "This tutorial has already been included in a claim."
    return True, ""


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            auth_login(request, form.get_user())
            return redirect("dashboard")
        messages.error(request, "Invalid email or password.")
    return render(request, "core/login.html", {"form": form})


@login_required
def logout_view(request):
    auth_logout(request)
    return redirect("login")


@login_required
def dashboard_redirect(request):
    role = request.user.role
    if role == User.Role.ADMIN:
        return redirect("admin_dashboard")
    if role == User.Role.LECTURER:
        return redirect("lecturer_dashboard")
    if role == User.Role.STUDENT:
        return redirect("student_dashboard")
    raise PermissionDenied("No role assigned to this account.")


# ---------------------------------------------------------------------------
# Student views
# ---------------------------------------------------------------------------

@role_required(User.Role.STUDENT)
def student_dashboard(request):
    student = request.user.student_profile
    course_ids = student.enrollments.values_list("course_id", flat=True)
    upcoming = sync_many(list(
        Tutorial.objects.filter(course_id__in=course_ids).exclude(status=Tutorial.Status.CANCELLED)
        .order_by("date", "start_time")
    ))
    upcoming = [t for t in upcoming if t.status in (Tutorial.Status.UPCOMING, Tutorial.Status.ACTIVE)][:5]
    recent_attended = StudentAttendance.objects.filter(student=student).select_related("tutorial").order_by("-joined_at")[:5]
    pending_feedback = []
    for att in StudentAttendance.objects.filter(student=student).select_related("tutorial"):
        if not Feedback.objects.filter(tutorial=att.tutorial, student=student).exists():
            pending_feedback.append(att.tutorial)
    recent_complaints = Complaint.objects.filter(student=student).order_by("-created_at")[:5]

    context = {
        "course_count": course_ids.count(),
        "upcoming": upcoming,
        "recent_attended": recent_attended,
        "pending_feedback": pending_feedback[:5],
        "recent_complaints": recent_complaints,
    }
    return render(request, "core/student_dashboard.html", context)


@role_required(User.Role.STUDENT)
def student_timetable(request):
    student = request.user.student_profile
    course_ids = student.enrollments.values_list("course_id", flat=True)
    tutorials = sync_many(list(
        Tutorial.objects.filter(course_id__in=course_ids).select_related("course", "lecturer__user")
        .order_by("date", "start_time")
    ))
    attended_ids = set(StudentAttendance.objects.filter(student=student).values_list("tutorial_id", flat=True))
    return render(request, "core/student_timetable.html", {
        "tutorials": tutorials, "attended_ids": attended_ids,
    })


@role_required(User.Role.STUDENT)
def join_tutorial(request, tutorial_id):
    student = request.user.student_profile
    tutorial = get_object_or_404(Tutorial, id=tutorial_id)

    if not CourseEnrollment.objects.filter(course=tutorial.course, student=student).exists():
        messages.error(request, "You are not enrolled in this course.")
        return redirect("student_timetable")

    if tutorial.is_cancelled():
        messages.error(request, "This tutorial has been cancelled.")
        return redirect("student_timetable")

    StudentAttendance.objects.get_or_create(tutorial=tutorial, student=student)
    messages.success(request, "Attendance recorded successfully.")
    return render(request, "core/join_tutorial.html", {"tutorial": tutorial})


@role_required(User.Role.STUDENT)
def submit_feedback(request, tutorial_id):
    student = request.user.student_profile
    tutorial = get_object_or_404(Tutorial, id=tutorial_id)

    if not StudentAttendance.objects.filter(tutorial=tutorial, student=student).exists():
        messages.error(request, "Only students who attended a tutorial may submit feedback.")
        return redirect("student_timetable")

    existing = Feedback.objects.filter(tutorial=tutorial, student=student).first()
    if existing:
        messages.info(request, "You have already submitted feedback for this tutorial.")
        return redirect("student_timetable")

    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.tutorial = tutorial
            feedback.student = student
            feedback.sentiment = analyze_sentiment(feedback.comment)
            feedback.save()
            messages.success(request, "Feedback submitted successfully.")
            return redirect("student_timetable")
    else:
        form = FeedbackForm()
    return render(request, "core/submit_feedback.html", {"form": form, "tutorial": tutorial})


@role_required(User.Role.STUDENT)
def submit_complaint(request, tutorial_id):
    student = request.user.student_profile
    tutorial = get_object_or_404(Tutorial, id=tutorial_id)

    if not CourseEnrollment.objects.filter(course=tutorial.course, student=student).exists():
        messages.error(request, "You are not enrolled in this course.")
        return redirect("student_timetable")

    if request.method == "POST":
        form = ComplaintForm(request.POST)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.tutorial = tutorial
            complaint.student = student
            complaint.save()
            messages.success(request, "Complaint submitted successfully.")
            return redirect("student_complaints")
    else:
        form = ComplaintForm()
    return render(request, "core/submit_complaint.html", {"form": form, "tutorial": tutorial})


@role_required(User.Role.STUDENT)
def student_complaints(request):
    student = request.user.student_profile
    complaints = Complaint.objects.filter(student=student).select_related("tutorial__course").order_by("-created_at")
    return render(request, "core/student_complaints.html", {"complaints": complaints})


# ---------------------------------------------------------------------------
# Lecturer views
# ---------------------------------------------------------------------------

@role_required(User.Role.LECTURER)
def lecturer_dashboard(request):
    lecturer = request.user.lecturer_profile
    tutorials = sync_many(list(Tutorial.objects.filter(lecturer=lecturer).order_by("date", "start_time")))
    upcoming = [t for t in tutorials if t.status in (Tutorial.Status.UPCOMING, Tutorial.Status.ACTIVE)][:5]
    eligible_count = sum(1 for t in tutorials if is_claim_eligible(t)[0])
    claims = Claim.objects.filter(lecturer=lecturer)
    avg_rating = Feedback.objects.filter(tutorial__lecturer=lecturer).aggregate(avg=Avg("rating"))["avg"]

    context = {
        "courses": Course.objects.filter(lecturer=lecturer, is_active=True),
        "upcoming": upcoming,
        "eligible_count": eligible_count,
        "pending_claims": claims.filter(status=Claim.Status.PENDING).count(),
        "approved_claims": claims.filter(status=Claim.Status.APPROVED).count(),
        "rejected_claims": claims.filter(status=Claim.Status.REJECTED).count(),
        "avg_rating": round(avg_rating, 1) if avg_rating else None,
    }
    return render(request, "core/lecturer_dashboard.html", context)


@role_required(User.Role.LECTURER)
def lecturer_timetable(request):
    lecturer = request.user.lecturer_profile
    tutorials = sync_many(list(
        Tutorial.objects.filter(lecturer=lecturer).select_related("course").order_by("date", "start_time")
    ))
    started_ids = set(LecturerAttendance.objects.filter(lecturer=lecturer).values_list("tutorial_id", flat=True))
    return render(request, "core/lecturer_timetable.html", {
        "tutorials": tutorials, "started_ids": started_ids,
    })


@role_required(User.Role.LECTURER)
def start_tutorial(request, tutorial_id):
    lecturer = request.user.lecturer_profile
    tutorial = get_object_or_404(Tutorial, id=tutorial_id, lecturer=lecturer)

    if tutorial.is_cancelled():
        messages.error(request, "This tutorial has been cancelled.")
        return redirect("lecturer_timetable")

    LecturerAttendance.objects.get_or_create(tutorial=tutorial, lecturer=lecturer)
    messages.success(request, "Attendance recorded successfully.")
    return render(request, "core/start_tutorial.html", {"tutorial": tutorial})


@role_required(User.Role.LECTURER)
def lecturer_feedback(request):
    lecturer = request.user.lecturer_profile
    feedback = Feedback.objects.filter(tutorial__lecturer=lecturer).select_related("tutorial__course", "student__user").order_by("-created_at")
    return render(request, "core/lecturer_feedback.html", {"feedback": feedback})


@role_required(User.Role.LECTURER)
def lecturer_complaints(request):
    lecturer = request.user.lecturer_profile
    complaints = Complaint.objects.filter(tutorial__lecturer=lecturer).select_related("tutorial__course").order_by("-created_at")
    return render(request, "core/lecturer_complaints.html", {"complaints": complaints})


@role_required(User.Role.LECTURER)
def eligible_tutorials(request):
    lecturer = request.user.lecturer_profile
    all_tutorials = Tutorial.objects.filter(lecturer=lecturer).select_related("course")
    eligible = []
    for t in all_tutorials:
        ok, _ = is_claim_eligible(t)
        if ok:
            eligible.append(t)

    if request.method == "POST":
        selected_ids = request.POST.getlist("tutorial_ids")
        if not selected_ids:
            messages.error(request, "Please select at least one tutorial to claim.")
        else:
            claim = Claim.objects.create(lecturer=lecturer)
            created_any = False
            for tid in selected_ids:
                tutorial = get_object_or_404(Tutorial, id=tid, lecturer=lecturer)
                ok, reason = is_claim_eligible(tutorial)
                if ok:
                    ClaimItem.objects.create(claim=claim, tutorial=tutorial)
                    created_any = True
            if created_any:
                messages.success(request, "Claim submitted successfully.")
                return redirect("my_claims")
            else:
                claim.delete()
                messages.error(request, "None of the selected tutorials are eligible for claiming.")

    return render(request, "core/eligible_tutorials.html", {
        "eligible": [{"tutorial": t, "attendees": t.student_attendances.count(),
                      "feedback_count": t.feedback_entries.count()} for t in eligible],
    })


@role_required(User.Role.LECTURER)
def my_claims(request):
    lecturer = request.user.lecturer_profile
    claims = Claim.objects.filter(lecturer=lecturer).prefetch_related("items__tutorial__course").order_by("-submitted_at")
    return render(request, "core/my_claims.html", {"claims": claims})


# ---------------------------------------------------------------------------
# Admin views (custom, beyond Django admin CRUD)
# ---------------------------------------------------------------------------

@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    tutorials = sync_many(list(Tutorial.objects.all()))
    context = {
        "total_students": Student.objects.count(),
        "total_lecturers": Lecturer.objects.count(),
        "total_courses": Course.objects.count(),
        "upcoming_tutorials": sum(1 for t in tutorials if t.status == Tutorial.Status.UPCOMING),
        "tutorials_conducted": sum(1 for t in tutorials if t.status == Tutorial.Status.COMPLETED),
        "tutorials_active": sum(1 for t in tutorials if t.status == Tutorial.Status.ACTIVE),
        "pending_claims": Claim.objects.filter(status=Claim.Status.PENDING).count(),
        "approved_claims": Claim.objects.filter(status=Claim.Status.APPROVED).count(),
        "rejected_claims": Claim.objects.filter(status=Claim.Status.REJECTED).count(),
        "total_complaints": Complaint.objects.count(),
        "avg_rating": Feedback.objects.aggregate(avg=Avg("rating"))["avg"],
        "recent_tutorials": sorted(tutorials, key=lambda t: (t.date, t.start_time), reverse=True)[:5],
        "recent_claims": Claim.objects.select_related("lecturer__user").order_by("-submitted_at")[:5],
        "recent_complaints": Complaint.objects.select_related("tutorial__course", "student__user").order_by("-created_at")[:5],
    }
    return render(request, "core/admin_dashboard.html", context)


@role_required(User.Role.ADMIN)
def admin_monitoring(request):
    tutorials = sync_many(list(Tutorial.objects.select_related("course", "lecturer__user").order_by("-date", "-start_time")))

    course_filter = request.GET.get("course", "")
    lecturer_filter = request.GET.get("lecturer", "")
    status_filter = request.GET.get("status", "")
    date_filter = request.GET.get("date", "")

    if course_filter:
        tutorials = [t for t in tutorials if str(t.course_id) == course_filter]
    if lecturer_filter:
        tutorials = [t for t in tutorials if str(t.lecturer_id) == lecturer_filter]
    if status_filter:
        tutorials = [t for t in tutorials if t.status == status_filter]
    if date_filter:
        tutorials = [t for t in tutorials if str(t.date) == date_filter]

    rows = []
    for t in tutorials:
        rows.append({
            "tutorial": t,
            "lecturer_attended": hasattr(t, "lecturer_attendance"),
            "student_count": t.student_attendances.count(),
            "feedback_count": t.feedback_entries.count(),
            "complaint_count": t.complaints.count(),
        })

    return render(request, "core/admin_monitoring.html", {
        "rows": rows,
        "courses": Course.objects.all(),
        "lecturers": Lecturer.objects.select_related("user"),
        "statuses": Tutorial.Status.choices,
        "filters": {"course": course_filter, "lecturer": lecturer_filter, "status": status_filter, "date": date_filter},
    })


@role_required(User.Role.ADMIN)
def admin_claims(request):
    status_filter = request.GET.get("status", "")
    claims = Claim.objects.select_related("lecturer__user").prefetch_related("items__tutorial__course").order_by("-submitted_at")
    if status_filter:
        claims = claims.filter(status=status_filter)
    return render(request, "core/admin_claims.html", {
        "claims": claims, "statuses": Claim.Status.choices, "status_filter": status_filter,
    })


@role_required(User.Role.ADMIN)
def admin_claim_detail(request, claim_id):
    claim = get_object_or_404(Claim.objects.select_related("lecturer__user").prefetch_related("items__tutorial__course"), id=claim_id)
    reject_form = ClaimRejectForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if claim.status != Claim.Status.PENDING:
            messages.error(request, "This claim has already been reviewed.")
            return redirect("admin_claim_detail", claim_id=claim.id)

        if action == "approve":
            claim.status = Claim.Status.APPROVED
            claim.reviewed_at = timezone.now()
            claim.reviewed_by = request.user
            claim.save()
            messages.success(request, "Claim approved successfully.")
            return redirect("admin_claims")

        elif action == "reject":
            reject_form = ClaimRejectForm(request.POST)
            if reject_form.is_valid():
                claim.status = Claim.Status.REJECTED
                claim.rejection_reason = reject_form.cleaned_data["rejection_reason"]
                claim.reviewed_at = timezone.now()
                claim.reviewed_by = request.user
                claim.save()
                messages.success(request, "Claim rejected successfully.")
                return redirect("admin_claims")
            else:
                messages.error(request, "Please provide a reason for rejecting this claim.")

    items_detail = []
    for item in claim.items.all():
        t = item.tutorial
        items_detail.append({
            "tutorial": t,
            "lecturer_attended": hasattr(t, "lecturer_attendance"),
            "student_count": t.student_attendances.count(),
            "feedback_count": t.feedback_entries.count(),
        })

    return render(request, "core/admin_claim_detail.html", {
        "claim": claim, "items_detail": items_detail, "reject_form": reject_form,
    })


@role_required(User.Role.ADMIN)
def admin_complaints(request):
    status_filter = request.GET.get("status", "")
    complaints = Complaint.objects.select_related("tutorial__course", "tutorial__lecturer__user", "student__user").order_by("-created_at")
    if status_filter:
        complaints = complaints.filter(status=status_filter)
    return render(request, "core/admin_complaints.html", {
        "complaints": complaints, "statuses": Complaint.Status.choices, "status_filter": status_filter,
    })


@role_required(User.Role.ADMIN)
def admin_complaint_detail(request, complaint_id):
    complaint = get_object_or_404(Complaint.objects.select_related("tutorial__course", "student__user"), id=complaint_id)
    if request.method == "POST":
        new_status = request.POST.get("status")
        response_text = request.POST.get("admin_response", "")
        if new_status in dict(Complaint.Status.choices):
            complaint.status = new_status
        complaint.admin_response = response_text
        complaint.save()
        messages.success(request, "Complaint updated successfully.")
        return redirect("admin_complaints")
    return render(request, "core/admin_complaint_detail.html", {
        "complaint": complaint, "statuses": Complaint.Status.choices,
    })


@role_required(User.Role.ADMIN)
def admin_appraisal(request):
    lecturers = Lecturer.objects.select_related("user")
    lecturer_id = request.GET.get("lecturer") or (lecturers.first().id if lecturers.exists() else None)
    report = None

    if lecturer_id:
        lecturer = get_object_or_404(Lecturer, id=lecturer_id)
        tutorials = Tutorial.objects.filter(lecturer=lecturer, status=Tutorial.Status.COMPLETED)
        feedback = Feedback.objects.filter(tutorial__lecturer=lecturer)
        total_feedback = feedback.count()

        sentiment_counts = feedback.values("sentiment").annotate(count=Count("id"))
        sentiment_map = {row["sentiment"]: row["count"] for row in sentiment_counts}
        pct = lambda key: round((sentiment_map.get(key, 0) / total_feedback) * 100, 1) if total_feedback else 0

        avg_rating = feedback.aggregate(avg=Avg("rating"))["avg"]
        total_attendance = StudentAttendance.objects.filter(tutorial__lecturer=lecturer).count()
        enrolled_total = sum(
            CourseEnrollment.objects.filter(course=t.course).count() for t in tutorials
        ) or 1
        avg_attendance_pct = round((total_attendance / enrolled_total) * 100, 1) if enrolled_total else 0

        complaints = Complaint.objects.filter(tutorial__lecturer=lecturer)
        resolved = complaints.filter(status__in=[Complaint.Status.RESOLVED, Complaint.Status.CLOSED]).count()

        report = {
            "lecturer": lecturer,
            "tutorials_conducted": tutorials.count(),
            "avg_rating": round(avg_rating, 1) if avg_rating else None,
            "positive_pct": pct("positive"),
            "neutral_pct": pct("neutral"),
            "negative_pct": pct("negative"),
            "avg_attendance_pct": avg_attendance_pct,
            "complaints": complaints.count(),
            "resolved": resolved,
            "summary": summarize_feedback(list(feedback.exclude(comment="").values_list("comment", flat=True))),
        }

    return render(request, "core/admin_appraisal.html", {"lecturers": lecturers, "report": report, "selected_id": int(lecturer_id) if lecturer_id else None})


@role_required(User.Role.ADMIN)
def admin_reports(request):
    tutorials = sync_many(list(Tutorial.objects.all()))
    feedback = Feedback.objects.all()
    total_feedback = feedback.count()
    sentiment_counts = feedback.values("sentiment").annotate(count=Count("id"))
    sentiment_map = {row["sentiment"]: row["count"] for row in sentiment_counts}

    context = {
        "tutorials_scheduled": len(tutorials),
        "tutorials_completed": sum(1 for t in tutorials if t.status == Tutorial.Status.COMPLETED),
        "tutorials_cancelled": sum(1 for t in tutorials if t.status == Tutorial.Status.CANCELLED),
        "by_course": Tutorial.objects.values("course__course_code").annotate(count=Count("id")).order_by("-count"),
        "by_lecturer": Tutorial.objects.values("lecturer__user__first_name", "lecturer__user__last_name").annotate(count=Count("id")).order_by("-count"),
        "student_attendance_total": StudentAttendance.objects.count(),
        "lecturer_attendance_total": LecturerAttendance.objects.count(),
        "feedback_total": total_feedback,
        "avg_rating": feedback.aggregate(avg=Avg("rating"))["avg"],
        "positive": sentiment_map.get("positive", 0),
        "neutral": sentiment_map.get("neutral", 0),
        "negative": sentiment_map.get("negative", 0),
        "complaints_total": Complaint.objects.count(),
        "complaints_open": Complaint.objects.filter(status=Complaint.Status.OPEN).count(),
        "complaints_resolved": Complaint.objects.filter(status__in=[Complaint.Status.RESOLVED, Complaint.Status.CLOSED]).count(),
        "claims_pending": Claim.objects.filter(status=Claim.Status.PENDING).count(),
        "claims_approved": Claim.objects.filter(status=Claim.Status.APPROVED).count(),
        "claims_rejected": Claim.objects.filter(status=Claim.Status.REJECTED).count(),
    }
    return render(request, "core/admin_reports.html", context)
