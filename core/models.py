from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError


class User(AbstractUser):
    """A single user table for all three roles."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        LECTURER = "lecturer", "Lecturer"
        STUDENT = "student", "Student"

    role = models.CharField(max_length=10, choices=Role.choices)

    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    def is_lecturer_role(self):
        return self.role == self.Role.LECTURER

    def is_student_role(self):
        return self.role == self.Role.STUDENT

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    student_id = models.CharField(max_length=20, unique=True)
    programme = models.CharField(max_length=100, blank=True)
    level = models.CharField(max_length=20, blank=True)
    is_active_account = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.student_id} - {self.user.get_full_name()}"


class Lecturer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="lecturer_profile")
    lecturer_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, blank=True)
    is_active_account = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.lecturer_id} - {self.user.get_full_name()}"


class Course(models.Model):
    course_code = models.CharField(max_length=20, unique=True)
    course_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    lecturer = models.ForeignKey(Lecturer, on_delete=models.SET_NULL, null=True, blank=True, related_name="courses")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.course_code} - {self.course_name}"


class CourseEnrollment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("course", "student")

    def __str__(self):
        return f"{self.student} in {self.course}"


class Tutorial(models.Model):
    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="tutorials")
    lecturer = models.ForeignKey(Lecturer, on_delete=models.CASCADE, related_name="tutorials")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    teams_link = models.URLField(max_length=500)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.UPCOMING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.course.course_code} - {self.date} {self.start_time}"

    def is_cancelled(self):
        return self.status == self.Status.CANCELLED


class StudentAttendance(models.Model):
    tutorial = models.ForeignKey(Tutorial, on_delete=models.CASCADE, related_name="student_attendances")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendances")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tutorial", "student")

    def __str__(self):
        return f"{self.student} attended {self.tutorial}"


class LecturerAttendance(models.Model):
    tutorial = models.OneToOneField(Tutorial, on_delete=models.CASCADE, related_name="lecturer_attendance")
    lecturer = models.ForeignKey(Lecturer, on_delete=models.CASCADE, related_name="attendances")
    started_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lecturer} started {self.tutorial}"


class Feedback(models.Model):
    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    tutorial = models.ForeignKey(Tutorial, on_delete=models.CASCADE, related_name="feedback_entries")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="feedback_entries")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    sentiment = models.CharField(max_length=10, choices=Sentiment.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("tutorial", "student")

    def clean(self):
        if not (1 <= self.rating <= 5):
            raise ValidationError("Rating must be between 1 and 5.")

    def __str__(self):
        return f"{self.student} rated {self.tutorial} {self.rating}/5"


class Complaint(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    tutorial = models.ForeignKey(Tutorial, on_delete=models.CASCADE, related_name="complaints")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="complaints")
    description = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    admin_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Complaint by {self.student} on {self.tutorial}"


class Claim(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    lecturer = models.ForeignKey(Lecturer, on_delete=models.CASCADE, related_name="claims")
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_claims")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Claim #{self.id} - {self.lecturer} - {self.status}"


class ClaimItem(models.Model):
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="items")
    tutorial = models.ForeignKey(Tutorial, on_delete=models.CASCADE, related_name="claim_items")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tutorial", "claim")

    def __str__(self):
        return f"{self.tutorial} in {self.claim}"
