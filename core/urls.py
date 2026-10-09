from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_redirect, name="dashboard"),

    # Student
    path("student/", views.student_dashboard, name="student_dashboard"),
    path("student/timetable/", views.student_timetable, name="student_timetable"),
    path("student/tutorial/<int:tutorial_id>/join/", views.join_tutorial, name="join_tutorial"),
    path("student/tutorial/<int:tutorial_id>/feedback/", views.submit_feedback, name="submit_feedback"),
    path("student/tutorial/<int:tutorial_id>/complaint/", views.submit_complaint, name="submit_complaint"),
    path("student/complaints/", views.student_complaints, name="student_complaints"),

    # Lecturer
    path("lecturer/", views.lecturer_dashboard, name="lecturer_dashboard"),
    path("lecturer/timetable/", views.lecturer_timetable, name="lecturer_timetable"),
    path("lecturer/tutorial/<int:tutorial_id>/start/", views.start_tutorial, name="start_tutorial"),
    path("lecturer/feedback/", views.lecturer_feedback, name="lecturer_feedback"),
    path("lecturer/complaints/", views.lecturer_complaints, name="lecturer_complaints"),
    path("lecturer/claims/eligible/", views.eligible_tutorials, name="eligible_tutorials"),
    path("lecturer/claims/", views.my_claims, name="my_claims"),

    # Admin
    path("admin-panel/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-panel/monitoring/", views.admin_monitoring, name="admin_monitoring"),
    path("admin-panel/claims/", views.admin_claims, name="admin_claims"),
    path("admin-panel/claims/<int:claim_id>/", views.admin_claim_detail, name="admin_claim_detail"),
    path("admin-panel/complaints/", views.admin_complaints, name="admin_complaints"),
    path("admin-panel/complaints/<int:complaint_id>/", views.admin_complaint_detail, name="admin_complaint_detail"),
    path("admin-panel/appraisal/", views.admin_appraisal, name="admin_appraisal"),
    path("admin-panel/reports/", views.admin_reports, name="admin_reports"),
]
