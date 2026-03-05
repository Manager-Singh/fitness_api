# from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth.decorators import user_passes_test
# from django.contrib.auth import get_user_model
# from workouts.models import WorkoutSession, WorkoutEntry
# from django.utils import timezone
# from datetime import timedelta
# from django.db import transaction

# User = get_user_model()  # Get the custom User model if any
from django.contrib.auth.decorators import user_passes_test
from datetime import timedelta
from django.db import transaction
from django.shortcuts import render,get_object_or_404, redirect
from django.utils import timezone

from django.contrib.auth import get_user_model
from workouts.models import WorkoutSession, WorkoutEntry
from nutration.models_log import NutraSession, NutraEntry

User = get_user_model()  # Get the custom User model if any 
# Only allow superusers (admins)
@user_passes_test(lambda u: u.is_superuser, login_url='/admin/login')
def index(request):
    users = User.objects.exclude(username='superadmin')
    return render(request, "stumalitationdata/index.html", {"users": users})




@user_passes_test(lambda u: u.is_superuser, login_url='/admin/login/')
def rollback_user_logs(request, user_id):
    user = get_object_or_404(User, id=user_id)

    with transaction.atomic():
        # ------------------ WORKOUT SESSIONS ------------------
        workout_sessions = WorkoutSession.objects.filter(user=user)
        for session in workout_sessions:
            new_date = session.date - timedelta(days=1)

            # Skip if target date already exists
            if WorkoutSession.objects.filter(
                user=session.user,
                user_routine=session.user_routine,
                date=new_date
            ).exists():
                continue  

            session.date = new_date
            session.save(update_fields=["date"])

            # shift workout entries created_at
            for entry in session.entries.all():
                entry.created_at -= timedelta(days=1)
                entry.save(update_fields=["created_at"])

        # ------------------ NUTRITION SESSIONS ------------------
        nutra_sessions = NutraSession.objects.filter(user=user)
        for session in nutra_sessions:
            new_date = session.date - timedelta(days=1)

            # Skip if target date already exists
            if NutraSession.objects.filter(
                user=session.user,
                date=new_date
            ).exists():
                continue  

            session.date = new_date
            session.save(update_fields=["date"])

            # shift nutra entries completed_at
            for entry in session.entries.all():
                entry.completed_at -= timedelta(days=1)
                entry.save(update_fields=["completed_at"])

    return redirect("stumalitationdata_index")