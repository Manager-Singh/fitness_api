import json
import traceback

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from posture_questions.dashboard_new_builder import build_dashboard_new_from_payload
from posture_questions.serializers_dashboard import DashboardNewResponseSerializer
from posture_questions.views import DashboardBaseUnavailable, build_dashboard_base_payload
from utils.age import get_user_age_exact
from utils.paywall_flags import is_teen_age, user_profile_sex


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
        lookup.add_argument(
            "--all-users",
            action="store_true",
            help="Smoke-test all active users without creating a test database.",
        )
        parser.add_argument(
            "--variant",
            choices=["all", "adult", "teen"],
            default="all",
            help="Filter --all-users by dashboard age band. Default: all.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum users to check with --all-users. Default: no limit.",
        )
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

    def _user_matches_variant(self, user, variant):
        if variant == "all":
            return True
        try:
            age_exact = float(get_user_age_exact(user) or 0.0)
        except Exception:
            age_exact = 0.0
        is_teen = is_teen_age(age_exact, gender=user_profile_sex(user), user=user)
        return bool(is_teen) if variant == "teen" else not bool(is_teen)

    def _smoke_user(self, user, options):
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
            return output
        except DashboardBaseUnavailable as exc:
            return {
                "success": False,
                "user_id": user.id,
                "error": "dashboard_base_unavailable",
                "status_code": getattr(exc.response, "status_code", None),
                "data": getattr(exc.response, "data", None),
            }
        except Exception as exc:
            output = {
                "success": False,
                "user_id": user.id,
                "error": str(exc),
                "type": exc.__class__.__name__,
            }
            if options.get("print_traceback"):
                output["traceback"] = traceback.format_exc()
            return output

    def handle(self, *args, **options):
        User = get_user_model()

        if options.get("all_users"):
            qs = User.objects.filter(is_active=True).order_by("id")
            variant = options.get("variant") or "all"
            limit = max(0, int(options.get("limit") or 0))
            checked = 0
            passed = 0
            failed = 0
            results = []
            for user in qs.iterator(chunk_size=200):
                if not self._user_matches_variant(user, variant):
                    continue
                result = self._smoke_user(user, options)
                checked += 1
                if result.get("success"):
                    passed += 1
                else:
                    failed += 1
                results.append(result)
                if limit and checked >= limit:
                    break

            output = {
                "success": failed == 0,
                "variant": variant,
                "checked": checked,
                "passed": passed,
                "failed": failed,
                "results": results,
            }
            self.stdout.write(json.dumps(output, indent=2, default=str))
            if failed:
                raise SystemExit(1)
            return

        try:
            user = self._get_user(options)
        except User.DoesNotExist as exc:
            raise CommandError(f"User not found: {exc}") from exc

        output = self._smoke_user(user, options)
        self.stdout.write(json.dumps(output, indent=2, default=str))
        if not output.get("success"):
            raise SystemExit(1)
