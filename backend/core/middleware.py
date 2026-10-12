from django.conf import settings
from django.http import JsonResponse


class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (settings.UPDATE_STATE / "maintenance").exists() and request.path not in [
            "/api/health/",
            "/api/updates/",
            "/api/session/",
        ]:
            return JsonResponse(
                {"detail": "به‌روزرسانی در حال اجرا است؛ کمی بعد تلاش کنید"}, status=503
            )
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
            response["X-Content-Type-Options"] = "nosniff"
        return response
