import json
import traceback

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from posture_questions.dashboard_new_builder import build_dashboard_new_from_payload
from posture_questions.serializers_dashboard import DashboardNewResponseSerializer
from posture_questions.views import DashboardBaseUnavailable, build_dashboard_base_payload


class Command(BaseCommand):
    help = (
        "Smoke-test dashboard-new against the configured database without creating "
        "a Django test database."
    )

    def add_arguments(self, parser):
        lookup = parser.add_mutually_exclusive_group(required=True)
        lookup.add_argument("--user-id", type=int, help="User id to test.")
        lookup.add_argument("--email", help="User email to test.")
        lookup.add_argument("--username", help="Username to test.")
        parser.add_argument(
            "--include-debug",
            action="store_true",
            help="Include debug fields in the dashboard-new builder.",
        )
        parser.add_argument(
            "--full",
            action="store_true",
            help="Print the full validated dashboard-new payload.",
        )
        parser.add_argument(
            "--print-traceback",
            action="store_true",
            help="Print Python traceback on failure.",
        )

    def _get_user(self, options):
        User = get_user_model()
        if options.get("user_id"):
            return User.objects.get(pk=options["user_id"])
        if options.get("email"):
            return User.objects.get(email=options["email"])
        return User.objects.get(username=options["username"])

    def handle(self, *args, **options):
        try:
            user = self._get_user(options)
        except get_user_model().DoesNotExist as exc:
            raise CommandError(f"User not found: {exc}") from exc

        try:
            base_payload = build_dashboard_base_payload(user)
            response_payload = build_dashboard_new_from_payload(
                user,
                base_payload,
                include_debug=bool(options.get("include_debug")),
            )
            serializer = DashboardNewResponseSerializer(data=response_payload)
            serializer.is_valid(raise_exception=True)
            data = dict(serializer.validated_data)
            dashboard = data.get("dashboard") or {}
            scan = dashboard.get("scan") or {}
            routine = dashboard.get("routine_progress") or {}

            if options.get("full"):
                output = {"success": True, "payload": data}
            else:
                output = {
                    "success": True,
                    "user_id": user.id,
                    "variant": dashboard.get("variant"),
                    "scan": {
                        "scan_completed": scan.get("scan_completed"),
                        "can_scan": scan.get("can_scan"),
                        "can_reassess": scan.get("can_reassess"),
                        "workouts_logged_today": scan.get("workouts_logged_today"),
                    },
                    "routine_progress": {
                        "exercises_done": routine.get("exercises_done"),
                        "total_exercises": routine.get("total_exercises"),
                        "daily_points": routine.get("daily_points"),
                    },
                    "genetic_average_cm": dashboard.get("genetic_average_cm"),
                    "daily_genetic_average_gain_cm": dashboard.get("daily_genetic_average_gain_cm"),
                }
            self.stdout.write(json.dumps(output, indent=2, default=str))
        except DashboardBaseUnavailable as exc:
            self.stdout.write(
                json.dumps(
                    {
                        "success": False,
                        "error": "dashboard_base_unavailable",
                        "status_code": getattr(exc.response, "status_code", None),
                        "data": getattr(exc.response, "data", None),
                    },
                    indent=2,
                    default=str,
                )
            )
            raise SystemExit(1)
        except Exception as exc:
            output = {
                "success": False,
                "error": str(exc),
                "type": exc.__class__.__name__,
            }
            if options.get("print_traceback"):
                output["traceback"] = traceback.format_exc()
            self.stdout.write(json.dumps(output, indent=2, default=str))
            raise SystemExit(1)
