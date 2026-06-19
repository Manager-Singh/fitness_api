from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from payment_packages.models import PaymentPackage
from user_profile.models import Payment, UserProfile


class Command(BaseCommand):
    help = "Create dummy users for API stress testing and export JWT tokens."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=100, help="Number of users to create.")
        parser.add_argument("--prefix", default="stress", help="Username/email prefix.")
        parser.add_argument("--domain", default="stress.local", help="Email domain.")
        parser.add_argument("--password", default="StressTest@12345", help="Password for all users.")
        parser.add_argument(
            "--tier",
            choices=["teen", "adult", "both"],
            default="teen",
            help="Account tier/profile type to create.",
        )
        parser.add_argument(
            "--output",
            default="/tmp/fitness_api_stress_users.jsonl",
            help="JSONL output file containing credentials and JWT tokens.",
        )
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Reset password for existing matching users.",
        )
        parser.add_argument(
            "--free",
            action="store_true",
            help="Do not create paid subscription rows for stress users.",
        )

    def handle(self, *args, **options):
        count = int(options["count"])
        if count <= 0:
            raise CommandError("--count must be greater than 0")

        prefix = str(options["prefix"]).strip()
        domain = str(options["domain"]).strip()
        password = str(options["password"])
        tier = str(options["tier"])
        output = Path(options["output"])
        reset_password = bool(options["reset_password"])
        make_paid = not bool(options["free"])

        if not prefix:
            raise CommandError("--prefix cannot be empty")
        if not domain or "@" in domain:
            raise CommandError("--domain must be a plain domain, e.g. stress.local")

        output.parent.mkdir(parents=True, exist_ok=True)

        User = get_user_model()
        created = 0
        updated = 0
        exported = []

        rows_to_create = []
        if tier == "both":
            teen_count = count // 2
            adult_count = count - teen_count
            rows_to_create.extend(("teen", i) for i in range(1, teen_count + 1))
            rows_to_create.extend(("adult", i) for i in range(1, adult_count + 1))
        else:
            rows_to_create.extend((tier, i) for i in range(1, count + 1))

        for row_tier, index in rows_to_create:
            tier_prefix = f"{prefix}_{row_tier}" if tier == "both" else prefix
            username = f"{tier_prefix}_{index:04d}"
            email = f"{username}@{domain}"
            user, was_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": username,
                    "name": f"Stress User {index:04d}",
                    "display_name": f"Stress User {index:04d}",
                    "profile_step": "completed",
                    "account_tier": row_tier,
                    "verified": timezone.now(),
                    "timezone": "UTC",
                    "country_code": "US",
                },
            )

            if was_created:
                user.set_password(password)
                created += 1
            else:
                updated += 1
                changed_fields = []
                if reset_password:
                    user.set_password(password)
                    changed_fields.append("password")
                if user.account_tier != row_tier:
                    user.account_tier = row_tier
                    changed_fields.append("account_tier")
                if user.profile_step != "completed":
                    user.profile_step = "completed"
                    changed_fields.append("profile_step")
                if user.verified is None:
                    user.verified = timezone.now()
                    changed_fields.append("verified")
                if changed_fields:
                    user.save(update_fields=changed_fields)

            if was_created:
                user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            if row_tier == "adult":
                birth_date = date.today() - timedelta(days=int(365.2425 * 25))
                age = "25"
                gender = "male"
                current_height_cm = "175"
                father_height_cm = "178"
                mother_height_cm = "165"
            else:
                birth_date = date.today() - timedelta(days=int(365.2425 * 15))
                age = "15"
                gender = "male"
                current_height_cm = "165"
                father_height_cm = "178"
                mother_height_cm = "165"

            profile.gender = gender
            profile.age = age
            profile.birth_date = birth_date
            profile.current_height_cm = current_height_cm
            profile.base_height_cm = profile.base_height_cm or current_height_cm
            profile.current_height_type = "cm"
            profile.father_height_cm = father_height_cm
            profile.father_height_type = "cm"
            profile.mother_height_cm = mother_height_cm
            profile.mother_height_type = "cm"
            profile.save()

            if make_paid:
                self._ensure_paid_subscription(user)

            refresh = RefreshToken.for_user(user)
            exported.append(
                {
                    "id": user.id,
                    "email": email,
                    "username": username,
                    "password": password,
                    "tier": row_tier,
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                }
            )

        with output.open("w", encoding="utf-8") as fh:
            for row in exported:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")

        self.stdout.write(
            self.style.SUCCESS(
                f"Stress users ready: created={created}, existing={updated}, exported={len(exported)}"
            )
        )
        self.stdout.write(f"Credentials/tokens file: {output}")
        self.stdout.write("Use these users only for QA/stress testing; the output file contains live JWTs.")

    def _ensure_paid_subscription(self, user):
        package, _ = PaymentPackage.objects.get_or_create(
            name="Stress Test Paid",
            defaults={
                "amount": 1,
                "is_free": False,
                "duration": "1m",
                "description": "Internal stress-test paid package.",
                "features": ["stress-test"],
            },
        )
        Payment.objects.get_or_create(
            user=user,
            payment_id=f"stress-paid-{user.id}",
            defaults={
                "package": package,
                "payment_status": "succeeded",
                "payment_method": "stress_test",
                "amount": package.amount,
                "currency": "usd",
                "complete_response": "{}",
            },
        )
