from django.urls import path
from core import api

urlpatterns = [
    path("api/session/", api.session),
    path("api/login/", api.login_view),
    path("api/logout/", api.logout_view),
    path("api/password/", api.password_change),
    path("api/health/", api.health),
    path("api/projects/", api.projects),
    path("api/reports/", api.management_reports),
    path("api/projects/<int:pk>/", api.project_detail),
    path("api/projects/<int:pk>/environments/", api.environments),
    path("api/projects/<int:pk>/machines/", api.machines),
    path("api/projects/<int:pk>/overview/", api.resources),
    path("api/projects/<int:pk>/memberships/", api.memberships),
    path("api/projects/<int:pk>/imports/", api.imports),
    path("api/projects/<int:pk>/exports/", api.exports),
    path("api/machines/<uuid:pk>/", api.machine_detail),
    path("api/machines/<uuid:pk>/activity/", api.activity),
    path("api/machines/<uuid:pk>/credential/", api.credentials),
    path("api/imports/<uuid:pk>/", api.import_detail),
    path("api/users/", api.users),
    path("api/audit/", api.audit_events),
    path('api/audit/<int:pk>/', api.audit_detail),
    path("api/settings/", api.system_settings),
    path("api/updates/", api.updates),
    path('api/updates/upload/', api.update_upload),
]
