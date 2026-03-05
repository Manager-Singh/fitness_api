import random
from rest_framework import generics, permissions
from .models import ExerciseItem
from .serializers import ExerciseItemSerializer,ExerciseSubmissionSerializer

class ExerciseItemListView(generics.ListAPIView):
    serializer_class = ExerciseItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        age = user.profile.age  # Assuming user.profile.age exists
        print(f"User age: {age}")

        # Determine user's age group
        if 13 <= age <= 17:
            age_group = '13-17'
        elif 18 <= age <= 20:
            age_group = '18-20'
        elif 21 <= age <= 29:
            age_group = '21-29'
        elif 30 <= age <= 39:
            age_group = '30-39'
        elif 40 <= age <= 49:
            age_group = '40-49'
        elif 50 <= age <= 59:
            age_group = '50-59'
        else:
            age_group = '60+'

        # Core 6 Exercises (HeightMax Essentials)
        core_6_exercises = ExerciseItem.objects.filter(
            category='core_six_height_max_essentials',
            age_group=age_group
        )

        # Core 4 Exercises (HeightMax Posture)
        core_4_exercises = ExerciseItem.objects.filter(
            category='core_four_height_max_posture',
            age_group=age_group
        )

        # Core 2 Exercises (HeightMax HGH)
        core_2_exercises = ExerciseItem.objects.filter(
            category='core_two_height_max_hgh',
            age_group=age_group
        )

        # Extras To Pick From (optional, no strict age group filtering — or you can add if needed)
        extras = ExerciseItem.objects.filter(
            category='extras_to_pick',
            #age_group=age_group  # <-- if you want even extras filtered by age group
        )

        # Randomly pick 3-4 extras
        extras_count = min(4, extras.count())
        random_extras = random.sample(list(extras), extras_count) if extras_count > 0 else []

        # Combine everything
        combined_exercises = list(core_6_exercises) + list(core_4_exercises) + list(core_2_exercises) + random_extras

        return combined_exercises

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context


class ExerciseSubmissionCreateView(generics.CreateAPIView):
    serializer_class = ExerciseSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
