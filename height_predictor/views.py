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
from .predictor import MODEL_VERSION, PredictorInputs, predict_optimized_height
from .serializers import (
    UltimatePredictionResultSerializer,
    UltimatePredictorInputSerializer,
)
from .services import defaults_from_profile, get_user_posture_recovery_cm

REQUIRED_CORE_FIELDS = ("sex", "age_years", "current_height_cm", "father_height_cm", "mother_height_cm")


class UltimateHeightPredictorView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        latest = (
            UltimateHeightPrediction.objects.filter(user=request.user, completed=True)
            .order_by("-computed_at")
            .first()
        )
        if not latest:
            return Response({"completed": False, "result": None})
        return Response({"completed": True, "result": UltimatePredictionResultSerializer(latest).data})

    def post(self, request):
        serializer = UltimatePredictorInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = serializer.validated_data

        # Merge: client-supplied values win over onboarding defaults.
        merged = defaults_from_profile(request.user)
        merged.update({k: v for k, v in client.items() if v is not None})

        missing = [f for f in REQUIRED_CORE_FIELDS if merged.get(f) in (None, "")]
        if missing:
            return Response(
                {
                    "error": "Missing required values for the prediction.",
                    "missing": missing,
                    "hint": "These are normally collected at onboarding; send them in the request if absent.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        posture_cm = get_user_posture_recovery_cm(request.user)

        inputs = PredictorInputs(
            sex=merged["sex"],
            age_years=float(merged["age_years"]),
            current_height_cm=float(merged["current_height_cm"]),
            father_height_cm=float(merged["father_height_cm"]),
            mother_height_cm=float(merged["mother_height_cm"]),
            voice_depth=int(merged.get("voice_depth", 0) or 0),
            facial_hair=int(merged.get("facial_hair", 0) or 0),
            body_hair=int(merged.get("body_hair", 0) or 0),
            adams_apple=int(merged.get("adams_apple", 0) or 0),
            menarche_status=int(merged.get("menarche_status", 0) or 0),
            growth_spurt_status=int(merged.get("growth_spurt_status", 0) or 0),
            recent_growth_cm=merged.get("recent_growth_cm"),
            wingspan_cm=merged.get("wingspan_cm"),
            wrist_circumference_cm=merged.get("wrist_circumference_cm"),
            weight_kg=merged.get("weight_kg"),
            shoe_size=merged.get("shoe_size"),
        )

        breakdown = predict_optimized_height(inputs, posture_cm)

        prediction = UltimateHeightPrediction.objects.create(
            user=request.user,
            sex=inputs.sex,
            age_years=inputs.age_years,
            current_height_cm=inputs.current_height_cm,
            father_height_cm=inputs.father_height_cm,
            mother_height_cm=inputs.mother_height_cm,
            voice_depth=inputs.voice_depth,
            facial_hair=inputs.facial_hair,
            body_hair=inputs.body_hair,
            adams_apple=inputs.adams_apple,
            menarche_status=inputs.menarche_status,
            growth_spurt_status=inputs.growth_spurt_status,
            recent_growth_cm=inputs.recent_growth_cm,
            wingspan_cm=inputs.wingspan_cm,
            wrist_circumference_cm=inputs.wrist_circumference_cm,
            weight_kg=inputs.weight_kg,
            shoe_size=inputs.shoe_size,
            posture_recovery_cm=breakdown["posture_recovery_cm"],
            genetic_potential_cm=breakdown["genetic_potential_cm"],
            true_optimized_cm=breakdown["true_optimized_cm"],
            band=breakdown["band"],
            model_version=MODEL_VERSION,
            completed=True,
            raw_inputs={k: v for k, v in merged.items()},
            breakdown=breakdown,
        )

        return Response(
            {"completed": True, "result": UltimatePredictionResultSerializer(prediction).data},
            status=status.HTTP_201_CREATED,
        )
