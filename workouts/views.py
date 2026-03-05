# workouts/views.py
from rest_framework import viewsets
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Exercise, AgeBracket, RoutineVariant
from .serializers import (
    ExerciseSerializer, AgeBracketSerializer, RoutineVariantSerializer
)


class ExerciseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Exercise.objects.all()
    serializer_class = ExerciseSerializer


class AgeBracketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AgeBracket.objects.all()
    serializer_class = AgeBracketSerializer


class RoutineVariantViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Main endpoint – returns the variant already matched to user age.
    """
    queryset = RoutineVariant.objects.prefetch_related(
        "prescriptions__exercise", "template", "age_bracket"
    )
    serializer_class = RoutineVariantSerializer

    @action(detail=False, url_path=r"by-age/(?P<age>\d+)")
    def by_age(self, request, age=None):
        age = int(age)

        qs = RoutineVariant.objects.filter(
            age_bracket__min_age__lte=age
        ).filter(
            Q(age_bracket__max_age__isnull=True) | Q(age_bracket__max_age__gte=age)
        ).prefetch_related("prescriptions__exercise", "template", "age_bracket")

        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)

        ser = self.get_serializer(qs, many=True)
        return Response(ser.data)
