from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    User, Student, Lecturer, Course, CourseEnrollment, Tutorial,
    StudentAttendance, LecturerAttendance, Feedback, Complaint, Claim, ClaimItem,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Role", {"fields": ("role", "email", "first_name", "last_name")}),
    )


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("student_id", "user", "programme", "level", "is_active_account")
    list_filter = ("programme", "level", "is_active_account")
    search_fields = ("student_id", "user__first_name", "user__last_name", "user__email")


@admin.register(Lecturer)
class LecturerAdmin(admin.ModelAdmin):
    list_display = ("lecturer_id", "user", "department", "is_active_account")
    list_filter = ("department", "is_active_account")
    search_fields = ("lecturer_id", "user__first_name", "user__last_name", "user__email")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("course_code", "course_name", "lecturer", "is_active")
    list_filter = ("is_active",)
    search_fields = ("course_code", "course_name")


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "created_at")
    list_filter = ("course",)
    search_fields = ("student__student_id", "course__course_code")


@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    list_display = ("course", "lecturer", "date", "start_time", "end_time", "status")
    list_filter = ("status", "course", "lecturer")
    date_hierarchy = "date"


@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ("tutorial", "student", "joined_at")
    readonly_fields = ("joined_at",)


@admin.register(LecturerAttendance)
class LecturerAttendanceAdmin(admin.ModelAdmin):
    list_display = ("tutorial", "lecturer", "started_at")
    readonly_fields = ("started_at",)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("tutorial", "student", "rating", "sentiment", "created_at")
    list_filter = ("sentiment", "rating")
    readonly_fields = ("sentiment",)


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("tutorial", "student", "status", "created_at")
    list_filter = ("status",)


class ClaimItemInline(admin.TabularInline):
    model = ClaimItem
    extra = 0


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("id", "lecturer", "status", "submitted_at", "reviewed_by")
    list_filter = ("status",)
    inlines = [ClaimItemInline]
    readonly_fields = ("submitted_at",)
