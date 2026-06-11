"""
Ultimate Height Predictor API (self-contained).

POST /api/predictor/ultimate-height  -> run the assessment, store + return the number.
GET  /api/predictor/ultimate-height  -> return the latest stored result + completion state.

This feature is isolated: it reads posture + onboarding values, runs the pure predictor, and
writes one row. It does NOT modify daily points, engines, the ledger, or the dashboard.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UltimateHeightPrediction
from .serializers import (
    UltimatePredictionResultSerializer,
    UltimatePredictorInputSerializer,
)
from .services import compute_and_store_prediction, get_latest_prediction


class UltimateHeightPredictorView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        latest = get_latest_prediction(request.user)
        if not latest:
            return Response({"completed": False, "result": None})
        return Response({"completed": True, "result": UltimatePredictionResultSerializer(latest).data})

    def post(self, request):
        serializer = UltimatePredictorInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prediction, err = compute_and_store_prediction(
            request.user,
            serializer.validated_data,
            source="api",
        )
        if err:
            return Response(err, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(
            {"completed": True, "result": UltimatePredictionResultSerializer(prediction).data},
            status=status.HTTP_201_CREATED,
        )
