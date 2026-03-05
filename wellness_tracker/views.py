# wellness/views.py

from rest_framework import generics, permissions
from .models import WellnessItem, WellnessSubmission
from .serializers import WellnessItemSerializer, WellnessSubmissionSerializer

class WellnessItemListView(generics.ListAPIView):
    serializer_class = WellnessItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        age = user.profile.age  # Assuming your User model has profile.age
        print(age)
        print(user.profile)
        print(user)
        if age >= 14 and age <= 20:
            return WellnessItem.objects.filter(category__in=[
                'growth_boost', 'sleep', 'sunlight', 'meditation', 'hydration'
            ])
        else:
            return WellnessItem.objects.filter(category__in=[
                'spine_support', 'posture_muscle'
            ])
            
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})  # << IMPORTANT
        return context        

class WellnessSubmissionCreateView(generics.CreateAPIView):
    serializer_class = WellnessSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        