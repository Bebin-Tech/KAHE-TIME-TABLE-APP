from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView
from accounts import views
from academics.views import records
from timetables import views as timetable_views
from reports import views as report_views
from academics.requests import requests as faculty_requests
from django.views.decorators.csrf import ensure_csrf_cookie

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/session/", views.session),
    path("api/users/", views.users),
    path("api/academic/<slug:resource>/", records),
    path("api/academic/<slug:resource>/<int:pk>/", records),
    path(
        "",
        ensure_csrf_cookie(
            login_required(TemplateView.as_view(template_name="shell.html"))
        ),
        name="home",
    ),
]
urlpatterns += [
    path("api/timetables/", timetable_views.tables),
    path("api/timetables/<int:pk>/", timetable_views.tables),
    path("api/editor-config/", timetable_views.editor_config),
    path("api/notifications/", timetable_views.notifications),
    path("api/audit/", timetable_views.audit_log),
    path("api/periods/", timetable_views.periods),
]
urlpatterns += [
    path("api/accounts/", views.account_records),
    path("api/accounts/<int:pk>/", views.account_records),
]
urlpatterns += [
    path("api/reports/", report_views.reports),
    path("api/exports/<slug:kind>/", report_views.export),
]
urlpatterns += [path("api/dashboard/", timetable_views.dashboard)]
urlpatterns += [path("api/conflicts/", timetable_views.conflicts)]
urlpatterns += [
    path("api/requests/", faculty_requests),
    path("api/requests/<int:pk>/", faculty_requests),
]
