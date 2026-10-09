import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    User, Student, Lecturer, Course, CourseEnrollment, Tutorial,
    StudentAttendance, LecturerAttendance, Feedback, Complaint, Claim, ClaimItem,
)
from core.sentiment import analyze_sentiment


class Command(BaseCommand):
    help = "Seed the database with demo data for development and demonstration."

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data...")

        # --- Admin -----------------------------------------------------
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults=dict(email="admin@example.com", first_name="System", last_name="Administrator",
                           role=User.Role.ADMIN, is_staff=True, is_superuser=True),
        )
        if created:
            admin_user.set_password("admin12345")
            admin_user.save()

        # --- Lecturers ---------------------------------------------------
        lecturer_defs = [
            ("john.doe", "John", "Doe", "L001", "Computer Science"),
            ("jane.smith", "Jane", "Smith", "L002", "Information Technology"),
        ]
        lecturers = []
        for username, first, last, lec_id, dept in lecturer_defs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults=dict(email=f"{username}@example.com", first_name=first, last_name=last, role=User.Role.LECTURER),
            )
            if created:
                user.set_password("lecturer123")
                user.save()
            lecturer, _ = Lecturer.objects.get_or_create(user=user, defaults=dict(lecturer_id=lec_id, department=dept))
            lecturers.append(lecturer)

        # --- Students ------------------------------------------------------
        student_defs = [
            ("student1", "Ama", "Boateng", "S001"),
            ("student2", "Kwame", "Mensah", "S002"),
            ("student3", "Efua", "Owusu", "S003"),
            ("student4", "Kojo", "Asante", "S004"),
            ("student5", "Adjoa", "Darko", "S005"),
            ("student6", "Yaw", "Appiah", "S006"),
        ]
        students = []
        for username, first, last, sid in student_defs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults=dict(email=f"{username}@example.com", first_name=first, last_name=last, role=User.Role.STUDENT),
            )
            if created:
                user.set_password("student123")
                user.save()
            student, _ = Student.objects.get_or_create(user=user, defaults=dict(student_id=sid, programme="BSc. Computer Science", level="300"))
            students.append(student)

        # --- Courses ---------------------------------------------------
        course_defs = [
            ("DCIT 401", "Information Technology Project", lecturers[0]),
            ("DCIT 405", "Distributed Computing", lecturers[0]),
            ("DCIT 318", "Software Engineering", lecturers[1]),
        ]
        courses = []
        for code, name, lecturer in course_defs:
            course, _ = Course.objects.get_or_create(
                course_code=code, defaults=dict(course_name=name, lecturer=lecturer, description=f"{name} course.")
            )
            courses.append(course)

        # --- Enrollments -------------------------------------------------
        for course in courses:
            for student in students[:5]:
                CourseEnrollment.objects.get_or_create(course=course, student=student)

        # --- Tutorials -----------------------------------------------------
        now = timezone.localtime()
        today = now.date()

        def make_tutorial(course, lecturer, date, start_time, end_time, status=None):
            t, _ = Tutorial.objects.get_or_create(
                course=course, lecturer=lecturer, date=date, start_time=start_time, end_time=end_time,
                defaults=dict(teams_link="https://teams.microsoft.com/l/meetup-join/demo", status=status or Tutorial.Status.UPCOMING),
            )
            if status:
                t.status = status
                t.save(update_fields=["status"])
            return t

        # Upcoming tutorial (next week)
        upcoming = make_tutorial(courses[0], lecturers[0], today + datetime.timedelta(days=7), datetime.time(18, 0), datetime.time(20, 0))

        # Active tutorial (happening right now)
        active_start = (now - datetime.timedelta(minutes=30)).time().replace(second=0, microsecond=0)
        active_end = (now + datetime.timedelta(minutes=30)).time().replace(second=0, microsecond=0)
        active = make_tutorial(courses[0], lecturers[0], today, active_start, active_end)

        # Completed tutorial with feedback, eligible for a claim
        eligible = make_tutorial(courses[0], lecturers[0], today - datetime.timedelta(days=7), datetime.time(18, 0), datetime.time(20, 0), status=Tutorial.Status.COMPLETED)
        LecturerAttendance.objects.get_or_create(tutorial=eligible, lecturer=lecturers[0])
        comments = [
            "The lecturer explained the topic very clearly.",
            "Good session, but the internet connection was a bit poor.",
            "The class was okay, nothing special.",
        ]
        for i, student in enumerate(students[:3]):
            StudentAttendance.objects.get_or_create(tutorial=eligible, student=student)
            comment = comments[i % len(comments)]
            Feedback.objects.get_or_create(
                tutorial=eligible, student=student,
                defaults=dict(rating=[5, 4, 3][i % 3], comment=comment, sentiment=analyze_sentiment(comment)),
            )

        # Completed & already-claimed tutorial
        claimed = make_tutorial(courses[0], lecturers[0], today - datetime.timedelta(days=14), datetime.time(18, 0), datetime.time(20, 0), status=Tutorial.Status.COMPLETED)
        LecturerAttendance.objects.get_or_create(tutorial=claimed, lecturer=lecturers[0])
        for student in students[:4]:
            StudentAttendance.objects.get_or_create(tutorial=claimed, student=student)
            comment = "The lecturer was excellent and answered every question."
            Feedback.objects.get_or_create(
                tutorial=claimed, student=student,
                defaults=dict(rating=5, comment=comment, sentiment=analyze_sentiment(comment)),
            )
        existing_claim = Claim.objects.filter(items__tutorial=claimed).first()
        if not existing_claim:
            approved_claim = Claim.objects.create(lecturer=lecturers[0], status=Claim.Status.APPROVED, reviewed_at=timezone.now(), reviewed_by=admin_user)
            ClaimItem.objects.create(claim=approved_claim, tutorial=claimed)

        # A cancelled tutorial
        make_tutorial(courses[1], lecturers[0], today + datetime.timedelta(days=3), datetime.time(16, 0), datetime.time(18, 0), status=Tutorial.Status.CANCELLED)

        # A tutorial with a complaint
        complaint_tutorial = make_tutorial(courses[2], lecturers[1], today - datetime.timedelta(days=3), datetime.time(14, 0), datetime.time(16, 0), status=Tutorial.Status.COMPLETED)
        LecturerAttendance.objects.get_or_create(tutorial=complaint_tutorial, lecturer=lecturers[1])
        StudentAttendance.objects.get_or_create(tutorial=complaint_tutorial, student=students[0])
        Complaint.objects.get_or_create(
            tutorial=complaint_tutorial, student=students[0],
            defaults=dict(description="Poor audio quality throughout the session.", status=Complaint.Status.OPEN),
        )

        # A second eligible tutorial for lecturer 2 (Jane Smith)
        eligible2 = make_tutorial(courses[2], lecturers[1], today - datetime.timedelta(days=5), datetime.time(10, 0), datetime.time(12, 0), status=Tutorial.Status.COMPLETED)
        LecturerAttendance.objects.get_or_create(tutorial=eligible2, lecturer=lecturers[1])
        for student in students[:2]:
            StudentAttendance.objects.get_or_create(tutorial=eligible2, student=student)
            comment = "The lecturer was late and the explanation was confusing."
            Feedback.objects.get_or_create(
                tutorial=eligible2, student=student,
                defaults=dict(rating=2, comment=comment, sentiment=analyze_sentiment(comment)),
            )

        # A pending claim for lecturer 1
        pending_tutorial = make_tutorial(courses[1], lecturers[0], today - datetime.timedelta(days=10), datetime.time(9, 0), datetime.time(11, 0), status=Tutorial.Status.COMPLETED)
        LecturerAttendance.objects.get_or_create(tutorial=pending_tutorial, lecturer=lecturers[0])
        for student in students[:3]:
            StudentAttendance.objects.get_or_create(tutorial=pending_tutorial, student=student)
            comment = "Great tutorial, very helpful."
            Feedback.objects.get_or_create(
                tutorial=pending_tutorial, student=student,
                defaults=dict(rating=5, comment=comment, sentiment=analyze_sentiment(comment)),
            )
        existing_pending = Claim.objects.filter(items__tutorial=pending_tutorial).first()
        if not existing_pending:
            pending_claim = Claim.objects.create(lecturer=lecturers[0], status=Claim.Status.PENDING)
            ClaimItem.objects.create(claim=pending_claim, tutorial=pending_tutorial)

        self.stdout.write(self.style.SUCCESS(
            "Seed data created.\n\n"
            "Login credentials (development only):\n"
            "  Admin:    admin / admin12345\n"
            "  Lecturer: john.doe / lecturer123  (also jane.smith / lecturer123)\n"
            "  Student:  student1 / student123  (student2..student6 follow the same pattern)\n"
        ))
