# from rest_framework import generics, permissions
# from .models import PostureImage, PostureReport
# from .serializers import PostureImageSerializer
# from user_profile.models import UserProfile
# import base64
# import openai
# import magic
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.parsers import MultiPartParser
# from rest_framework import status
# from django.conf import settings
# import json
# from django.utils import timezone


# openai.api_key = settings.OPENAI_API_KEY

# class PostureImageUploadView(generics.CreateAPIView):
#     serializer_class = PostureImageSerializer
#     permission_classes = [permissions.IsAuthenticated]



# def encode_image(file):
#     mime_type = magic.from_buffer(file.read(2048), mime=True)
#     file.seek(0)
#     encoded = base64.b64encode(file.read()).decode('utf-8')
#     return f"data:{mime_type};base64,{encoded}"

# class FullPostureAnalysisAPIView(APIView):
#     parser_classes = [MultiPartParser]
   
#     def post(self, request):
#         print(request.FILES)
#         front_image = request.FILES.get('front')
#         side_image = request.FILES.get('side')
#         back_image = request.FILES.get('back')
#         t_pose = request.FILES.get('t_pose')
#         t_pose_data = request.data.get("t_pose_data")

#         if not all([front_image, side_image, back_image,t_pose]):
#             return Response({'error': 'All three images (front, side, back) are required.'}, status=400)

#         try:
#             front_encoded = encode_image(front_image)
#             side_encoded = encode_image(side_image)
#             back_encoded = encode_image(back_image)
#             t_pose_encoded = encode_image(t_pose)

#             messages = [
#                  {
#                     "role": "system",
#                     "content": (
#                         "You are a professional posture analyst. You will receive 3 anonymous images (front, side, back and T-Pose) of a anonymous person's posture."
#                         "Your task is to assess posture alignment and provide a detailed JSON report only.\n\n"
#                         "**IMPORTANT INSTRUCTIONS**:\n"
#                         "- Return ONLY valid JSON (no markdown, no explanation, no prefix like 'Here's the JSON')\n"
#                         "- Do NOT wrap the response in ```json or say anything else\n"
#                         "- Output must start directly with a JSON object\n\n"
#                         "**OUTPUT FORMAT:**\n"
#                         "{\n"
#                         "  \"summary\": {\n"
#                         "    \"summary\": string,\n"
#                         "    \"max_height_gain_inches\": float,\n"
#                         "    \"note\": string,\n"
#                         "    \"spinal_compression\": int,\n"
#                         "    \"posture_collapse\": int,\n"
#                         "    \"pelvic_tilt_back\": int,\n"
#                         "    \"leg_hamstring\": int,\n"
#                         "    \"recommendations\": [\n"
#                         "      {\"title\": string, \"description\": string},\n"
#                         "      ... 5 items total\n"
#                         "    ]\n"
#                         "  },\n"
#                         "  \"optimization_breakdown\": {\n"
#                         "    \"spinal_compression\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#                         "    \"posture_collapse\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#                         "    \"pelvic_tilt_back\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#                         "    \"leg_hamstring\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int}\n"
#                         "  }\n"
#                         "}\n\n"
#                         "Begin your response directly with this JSON object."
#                     )
#                 },
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": "Analyze my posture based on these three views."},
#                         {"type": "image_url", "image_url": {"url": front_encoded}},
#                         {"type": "image_url", "image_url": {"url": side_encoded}},
#                         {"type": "image_url", "image_url": {"url": back_encoded}},
#                         {"type": "image_url", "image_url": {"url": t_pose_encoded}},
                        
#                     ]
#                 }
#             ]

#             response = openai.chat.completions.create(
#                 model="gpt-4o",
#                 messages=messages,
#                 max_tokens=1500
#             )

#             analysis_raw = response.choices[0].message.content
#             analysis = json.loads(analysis_raw)
#             print(analysis)
#             PostureReport.objects.create(user=request.user, data=analysis,t_pose_data=t_pose_data)
#             profile   = UserProfile.objects.get(user=request.user)
#             profile.last_scan = timezone.now()
#             profile.save()

#             return Response({'analysis': analysis})

#         except Exception as e:
#             return Response({'error': str(e),'analysis_raw':analysis_raw}, status=500)









# #--------------------------------------------------------------

# from rest_framework import generics, permissions, status
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.parsers import MultiPartParser

# from django.conf import settings
# from django.utils import timezone

# from .models import PostureImage, PostureReport
# from .serializers import PostureImageSerializer
# from user_profile.models import UserProfile

# import base64
# import json
# import magic
# import openai


# # ---------------------------------------------------------
# # OpenAI Config
# # ---------------------------------------------------------
# openai.api_key = settings.OPENAI_API_KEY


# # ---------------------------------------------------------
# # Upload posture images (unchanged)
# # ---------------------------------------------------------
# class PostureImageUploadView(generics.CreateAPIView):
#     serializer_class = PostureImageSerializer
#     permission_classes = [permissions.IsAuthenticated]


# # ---------------------------------------------------------
# # Encode image → base64
# # ---------------------------------------------------------
# def encode_image(file):
#     mime_type = magic.from_buffer(file.read(2048), mime=True)
#     file.seek(0)
#     encoded = base64.b64encode(file.read()).decode("utf-8")
#     return f"data:{mime_type};base64,{encoded}"


# # ---------------------------------------------------------
# # SAFE JSON loader for AI responses (CRITICAL)
# # ---------------------------------------------------------
# def safe_json_loads(raw_text: str):
#     if not raw_text:
#         raise ValueError("Empty AI response")

#     raw_text = raw_text.strip()

#     start = raw_text.find("{")
#     end = raw_text.rfind("}")

#     if start == -1 or end == -1:
#         raise ValueError("No JSON object found in AI response")

#     return json.loads(raw_text[start:end + 1])


# # ---------------------------------------------------------
# # ADVANCED: Deterministic posture math from T-pose landmarks
# # ---------------------------------------------------------
# def analyze_t_pose_metrics(t_pose_data: dict):
#     landmarks = t_pose_data.get("landmarks", {})

#     def x(name): return landmarks.get(name, {}).get("x", 0)
#     def y(name): return landmarks.get(name, {}).get("y", 0)

#     shoulder_tilt_px = abs(y("leftShoulder") - y("rightShoulder"))
#     hip_tilt_px = abs(y("leftHip") - y("rightHip"))

#     left_arm_px = abs(x("leftWrist") - x("leftShoulder"))
#     right_arm_px = abs(x("rightWrist") - x("rightShoulder"))
#     arm_asymmetry_px = abs(left_arm_px - right_arm_px)

#     shoulder_center_y = (y("leftShoulder") + y("rightShoulder")) / 2
#     hip_center_y = (y("leftHip") + y("rightHip")) / 2
#     spine_height_px = hip_center_y - shoulder_center_y

#     spinal_compression = min(100, int(spine_height_px / 28)) if spine_height_px > 0 else 0
#     posture_collapse = min(100, int(shoulder_tilt_px / 4))
#     pelvic_tilt_back = min(100, int(hip_tilt_px / 5))
#     leg_hamstring = min(100, int(arm_asymmetry_px / 6))

#     max_height_gain_inches = round(min(1.2, spinal_compression * 0.012), 2)

#     return {
#         "spinal_compression": spinal_compression,
#         "posture_collapse": posture_collapse,
#         "pelvic_tilt_back": pelvic_tilt_back,
#         "leg_hamstring": leg_hamstring,
#         "max_height_gain_inches": max_height_gain_inches,
#     }


# # ---------------------------------------------------------
# # FULL POSTURE ANALYSIS API (T-POSE OPTIONAL + SAFE)
# # ---------------------------------------------------------
# class FullPostureAnalysisAPIView(APIView):
#     parser_classes = [MultiPartParser]
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         front = request.FILES.get("front")
#         side = request.FILES.get("side")
#         back = request.FILES.get("back")
#         t_pose_image = request.FILES.get("t_pose")
#         t_pose_data = request.data.get("t_pose_data")

#         # Front / Side / Back are mandatory
#         if not all([front, side, back]):
#             return Response(
#                 {"error": "front, side and back images are required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             # ---------------------------------------------
#             # 1️⃣ Optional T-pose metrics
#             # ---------------------------------------------
#             metrics = None
#             t_pose_json = None

#             if t_pose_data:
#                 try:
#                     t_pose_json = json.loads(t_pose_data)
#                     metrics = analyze_t_pose_metrics(t_pose_json)
#                 except Exception:
#                     metrics = None

#             # ---------------------------------------------
#             # 2️⃣ Encode images
#             # ---------------------------------------------
#             images = [
#                 encode_image(front),
#                 encode_image(side),
#                 encode_image(back),
#             ]

#             if t_pose_image:
#                 images.append(encode_image(t_pose_image))

#             # ---------------------------------------------
#             # 3️⃣ Build system prompt dynamically
#             # ---------------------------------------------
#             if metrics:
#                 system_prompt = (
#                     "You are a professional posture analyst.\n"
#                     "The numeric posture metrics below are FINAL and computed mathematically.\n"
#                     "DO NOT modify numbers.\n"
#                     "Explain posture and give corrective advice only.\n"
#                     "Return ONLY valid JSON.\n\n"
#                     f"METRICS:\n{json.dumps(metrics, indent=2)}\n\n"
#                     "OUTPUT FORMAT:\n"
#                     "{\n"
#                     "  \"summary\": {\n"
#                     "    \"summary\": string,\n"
#                     "    \"note\": string,\n"
#                     "    \"recommendations\": [{\"title\": string, \"description\": string}]\n"
#                     "  },\n"
#                     "  \"optimization_breakdown\": {\n"
#                     "    \"spinal_compression\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#                     "    \"posture_collapse\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#                     "    \"pelvic_tilt_back\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#                     "    \"leg_hamstring\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int}\n"
#                     "  }\n"
#                     "}"
#                 )
#             else:
#                 system_prompt = (
#                     "You are a professional posture analyst.\n"
#                     "Analyze posture using images only.\n"
#                     "Provide best-effort estimates.\n"
#                     "Return ONLY valid JSON.\n\n"
#                     "OUTPUT FORMAT:\n"
#                     "{\n"
#                     "  \"summary\": {\n"
#                     "    \"summary\": string,\n"
#                     "    \"note\": string,\n"
#                     "    \"recommendations\": [{\"title\": string, \"description\": string}]\n"
#                     "  },\n"
#                     "  \"optimization_breakdown\": {\n"
#                     "    \"spinal_compression\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#                     "    \"posture_collapse\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#                     "    \"pelvic_tilt_back\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#                     "    \"leg_hamstring\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int}\n"
#                     "  }\n"
#                     "}"
#                 )

#             # ---------------------------------------------
#             # 4️⃣ OpenAI call
#             # ---------------------------------------------
#             response = openai.chat.completions.create(
#                 model="gpt-4o",
#                 messages=[
#                     {"role": "system", "content": system_prompt},
#                     {
#                         "role": "user",
#                         "content": [
#                             {"type": "text", "text": "Analyze posture and suggest improvements."},
#                             *[
#                                 {"type": "image_url", "image_url": {"url": img}}
#                                 for img in images
#                             ],
#                         ],
#                     },
#                 ],
#                 max_tokens=900,
#             )

#             raw_output = response.choices[0].message.content
#             ai_result = safe_json_loads(raw_output)

#             # ---------------------------------------------
#             # 5️⃣ Merge final response
#             # ---------------------------------------------
#             final_analysis = {
#                 "summary": {
#                     "summary": ai_result["summary"]["summary"],
#                     "note": ai_result["summary"]["note"],
#                     "recommendations": ai_result["summary"]["recommendations"],
#                 },
#                 "optimization_breakdown": ai_result["optimization_breakdown"],
#             }

#             if metrics:
#                 final_analysis["summary"].update(metrics)

#             # ---------------------------------------------
#             # 6️⃣ Save report
#             # ---------------------------------------------
#             PostureReport.objects.create(
#                 user=request.user,
#                 data=final_analysis,
#                 t_pose_data=t_pose_json,
#             )

#             profile = UserProfile.objects.get(user=request.user)
#             profile.last_scan = timezone.now()
#             profile.save()

#             return Response({"analysis": final_analysis})

#         except Exception as e:
#             # Graceful fallback (NO 500 crash)
#             fallback = {
#                 "summary": {
#                     "summary": "Posture analysis could not be fully generated.",
#                     "note": "Please retry with clearer images.",
#                     "recommendations": [],
#                 },
#                 "optimization_breakdown": {},
#             }

#             return Response(
#                 {
#                     "error": str(e),
#                     "analysis": fallback,
#                 },
#                 status=status.HTTP_200_OK,
#             )


#----------------------------------------------------------------------
# from rest_framework import generics, permissions, status
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.parsers import MultiPartParser

# from django.conf import settings
# from django.utils import timezone

# from .models import PostureImage, PostureReport
# from .serializers import PostureImageSerializer
# from user_profile.models import UserProfile

# import base64
# import json
# import magic
# import openai
# import logging


# # ---------------------------------------------------------
# # Logger
# # ---------------------------------------------------------
# logger = logging.getLogger(__name__)


# # ---------------------------------------------------------
# # OpenAI Config
# # ---------------------------------------------------------
# openai.api_key = settings.OPENAI_API_KEY


# # ---------------------------------------------------------
# # Upload posture images
# # ---------------------------------------------------------
# class PostureImageUploadView(generics.CreateAPIView):
#     serializer_class = PostureImageSerializer
#     permission_classes = [permissions.IsAuthenticated]


# # ---------------------------------------------------------
# # Encode image → base64
# # ---------------------------------------------------------
# def encode_image(file):
#     mime_type = magic.from_buffer(file.read(2048), mime=True)
#     file.seek(0)
#     encoded = base64.b64encode(file.read()).decode("utf-8")
#     return f"data:{mime_type};base64,{encoded}"


# # ---------------------------------------------------------
# # Safe JSON loader (AI only)
# # ---------------------------------------------------------
# def safe_json_loads(raw_text):
#     if not raw_text:
#         raise ValueError("Empty AI response")

#     raw_text = raw_text.strip()
#     start = raw_text.find("{")
#     end = raw_text.rfind("}")

#     if start == -1 or end == -1:
#         raise ValueError("Invalid JSON from AI")

#     return json.loads(raw_text[start:end + 1])


# # ---------------------------------------------------------
# # HARDENED T-POSE PARSER (FIXES DOUBLE JSON)
# # ---------------------------------------------------------
# def parse_t_pose_data(raw_value):
#     """
#     Accepts:
#     - dict
#     - JSON string
#     - DOUBLE JSON string
#     Returns dict or None
#     """

#     if raw_value in (None, "", {}):
#         return None

#     parsed = raw_value

#     try:
#         # Unwrap JSON up to 3 times (safe)
#         for _ in range(3):
#             if isinstance(parsed, str):
#                 parsed = json.loads(parsed)

#         if isinstance(parsed, dict):
#             return parsed

#     except Exception as e:
#         logger.error(f"T-pose parsing failed: {e}")

#     return None


# # ---------------------------------------------------------
# # Deterministic posture math (DICT ONLY)
# # ---------------------------------------------------------
# def analyze_t_pose_metrics(t_pose_data: dict):
#     if not isinstance(t_pose_data, dict):
#         raise ValueError("t_pose_data must be a dict")

#     landmarks = t_pose_data.get("landmarks")
#     if not isinstance(landmarks, dict):
#         raise ValueError("landmarks missing")

#     required = [
#         "leftShoulder", "rightShoulder",
#         "leftHip", "rightHip",
#         "leftWrist", "rightWrist"
#     ]

#     for key in required:
#         if key not in landmarks:
#             raise ValueError(f"Missing landmark: {key}")

#     def x(k): return landmarks[k]["x"]
#     def y(k): return landmarks[k]["y"]

#     shoulder_tilt = abs(y("leftShoulder") - y("rightShoulder"))
#     hip_tilt = abs(y("leftHip") - y("rightHip"))

#     left_arm = abs(x("leftWrist") - x("leftShoulder"))
#     right_arm = abs(x("rightWrist") - x("rightShoulder"))
#     arm_asymmetry = abs(left_arm - right_arm)

#     shoulder_center = (y("leftShoulder") + y("rightShoulder")) / 2
#     hip_center = (y("leftHip") + y("rightHip")) / 2
#     spine_height = hip_center - shoulder_center

#     spinal_compression = max(0, int(spine_height / 28))
#     posture_collapse = max(0, int(shoulder_tilt / 4))
#     pelvic_tilt_back = max(0, int(hip_tilt / 5))
#     leg_hamstring = max(0, int(arm_asymmetry / 6))

#     return {
#         "max_height_gain_inches": round(min(1.5, spinal_compression * 0.015), 2),
#         "spinal_compression": min(100, spinal_compression),
#         "posture_collapse": min(100, posture_collapse),
#         "pelvic_tilt_back": min(100, pelvic_tilt_back),
#         "leg_hamstring": min(100, leg_hamstring),
#     }


# # ---------------------------------------------------------
# # FULL POSTURE ANALYSIS API (FINAL)
# # ---------------------------------------------------------
# class FullPostureAnalysisAPIView(APIView):
#     parser_classes = [MultiPartParser]
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):

#         front = request.FILES.get("front")
#         side = request.FILES.get("side")
#         back = request.FILES.get("back")
#         t_pose_image = request.FILES.get("t_pose")
#         raw_t_pose_data = request.data.get("t_pose_data")

#         if not all([front, side, back]):
#             return Response(
#                 {"error": "front, side and back images are required"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         # -------------------------------------------------
#         # DEFAULT METRICS
#         # -------------------------------------------------
#         metrics = {
#             "max_height_gain_inches": 0,
#             "spinal_compression": 0,
#             "posture_collapse": 0,
#             "pelvic_tilt_back": 0,
#             "leg_hamstring": 0,
#         }

#         # -------------------------------------------------
#         # PARSE T-POSE SAFELY (FINAL FIX)
#         # -------------------------------------------------
#         t_pose_data = parse_t_pose_data(raw_t_pose_data)
#         logger.warning(f"T-pose FINAL type: {type(t_pose_data)}")

#         if t_pose_data:
#             try:
#                 metrics = analyze_t_pose_metrics(t_pose_data)
#             except Exception as e:
#                 logger.error(f"T-pose metrics failed: {e}")

#         # -------------------------------------------------
#         # Encode images
#         # -------------------------------------------------
#         images = [
#             encode_image(front),
#             encode_image(side),
#             encode_image(back),
#         ]
#         if t_pose_image:
#             images.append(encode_image(t_pose_image))

#         # -------------------------------------------------
#         # PROMPT (UNCHANGED MEANING)
#         # -------------------------------------------------
#         system_prompt = (
#             "You are a professional posture analyst.\n"
#             "Numeric posture values are calculated by backend.\n"
#             f"METRICS:\n{json.dumps(metrics, indent=2)}\n\n"
#             "Numeric posture values are already calculated by the backend.\n"
#             "DO NOT recalculate or modify them.\n"
#             "Rules:\n"
#             "- current_loss_cm is derived proportionally from metric severity\n"
#             "- percent_optimized = 100 - (current_loss_cm / max_loss_cm * 100)\n"
#             "- Clamp percent_optimized between 0 and 100\n"
#             "- ONLY explain, recommend, and convert to optimization_breakdown\n"
#             "ONLY write explanation and recommendations.\n"
#             "Return ONLY valid JSON.\n\n"
#             "OUTPUT FORMAT:\n"
#             "{\n"
#             "  \"summary\": {\n"
#             "    \"summary\": string,\n"
#             "    \"note\": string,\n"
#             "    \"recommendations\": [{\"title\": string, \"description\": string}]\n"
#             "  },\n"
#             "  \"optimization_breakdown\": {\n"
#             "    \"spinal_compression\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#             "    \"posture_collapse\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#             "    \"pelvic_tilt_back\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int},\n"
#             "    \"leg_hamstring\": {\"current_loss_cm\": float, \"max_loss_cm\": float, \"percent_optimized\": int}\n"
#             "  }\n"
#             "}"
#         )

#         # -------------------------------------------------
#         # OpenAI call
#         # -------------------------------------------------
#         response = openai.chat.completions.create(
#             model="gpt-4o",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": "Analyze posture and suggest improvements."},
#                         *[
#                             {"type": "image_url", "image_url": {"url": img}}
#                             for img in images
#                         ],
#                     ],
#                 },
#             ],
#             max_tokens=1500,
#         )

#         ai_result = safe_json_loads(response.choices[0].message.content)

#         # -------------------------------------------------
#         # FINAL RESPONSE (SCHEMA PRESERVED)
#         # -------------------------------------------------
#         final_response = {
#             "analysis": {
#                 "summary": {
#                     "summary": ai_result["summary"].get("summary", ""),
#                     "max_height_gain_inches": metrics["max_height_gain_inches"],
#                     "note": ai_result["summary"].get("note", ""),
#                     "spinal_compression": metrics["spinal_compression"],
#                     "posture_collapse": metrics["posture_collapse"],
#                     "pelvic_tilt_back": metrics["pelvic_tilt_back"],
#                     "leg_hamstring": metrics["leg_hamstring"],
#                     "recommendations": ai_result["summary"].get("recommendations", []),
#                 },
#                 "optimization_breakdown": ai_result.get("optimization_breakdown", {
#                     "spinal_compression": {"current_loss_cm": 0, "max_loss_cm": 0, "percent_optimized": 0},
#                     "posture_collapse": {"current_loss_cm": 0, "max_loss_cm": 0, "percent_optimized": 0},
#                     "pelvic_tilt_back": {"current_loss_cm": 0, "max_loss_cm": 0, "percent_optimized": 0},
#                     "leg_hamstring": {"current_loss_cm": 0, "max_loss_cm": 0, "percent_optimized": 0},
#                 }),
#             }
#         }

#         # -------------------------------------------------
#         # Save report
#         # -------------------------------------------------
#         PostureReport.objects.create(
#             user=request.user,
#             data=final_response,
#             t_pose_data=t_pose_data,
#         )

#         profile = UserProfile.objects.get(user=request.user)
#         profile.last_scan = timezone.now()
#         profile.save()

#         return Response(final_response)


#--------------------------------------------------------
# from rest_framework import generics, permissions, status
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.parsers import MultiPartParser

# from django.conf import settings
# from django.utils import timezone

# from .models import PostureImage, PostureReport
# from .serializers import PostureImageSerializer
# from user_profile.models import UserProfile

# import base64
# import json
# import magic
# import logging

# from openai import OpenAI


# # =========================================================
# # LOGGER
# # =========================================================
# logger = logging.getLogger(__name__)


# # =========================================================
# # OPENAI CLIENT (RESPONSES API)
# # =========================================================
# client = OpenAI(api_key=settings.OPENAI_API_KEY)


# # =========================================================
# # UPLOAD POSTURE IMAGE API
# # =========================================================
# class PostureImageUploadView(generics.CreateAPIView):
#     serializer_class = PostureImageSerializer
#     permission_classes = [permissions.IsAuthenticated]


# # =========================================================
# # IMAGE → BASE64
# # =========================================================
# def encode_image(file):
#     mime_type = magic.from_buffer(file.read(2048), mime=True)
#     file.seek(0)
#     encoded = base64.b64encode(file.read()).decode("utf-8")
#     return f"data:{mime_type};base64,{encoded}"


# # =========================================================
# # SAFE JSON LOAD (AI OUTPUT)
# # =========================================================
# def safe_json_loads(raw_text: str):
#     if not raw_text:
#         raise ValueError("Empty AI response")

#     raw_text = raw_text.strip()
#     start = raw_text.find("{")
#     end = raw_text.rfind("}")

#     if start == -1 or end == -1:
#         raise ValueError("Invalid JSON from AI")

#     return json.loads(raw_text[start:end + 1])


# # =========================================================
# # SAFE T-POSE PARSER
# # =========================================================
# def parse_t_pose_data(raw_value):
#     if raw_value in (None, "", {}):
#         return None

#     parsed = raw_value
#     try:
#         for _ in range(3):
#             if isinstance(parsed, str):
#                 parsed = json.loads(parsed)
#         if isinstance(parsed, dict):
#             return parsed
#     except Exception as e:
#         logger.error(f"T-pose parsing failed: {e}")

#     return None


# # =========================================================
# # BACKEND POSTURE METRICS (DETERMINISTIC)
# # =========================================================
# def analyze_t_pose_metrics(t_pose_data: dict):
#     landmarks = t_pose_data.get("landmarks", {})

#     required = [
#         "leftShoulder", "rightShoulder",
#         "leftHip", "rightHip",
#         "leftWrist", "rightWrist"
#     ]
#     for key in required:
#         if key not in landmarks:
#             raise ValueError(f"Missing landmark: {key}")

#     def x(k): return landmarks[k]["x"]
#     def y(k): return landmarks[k]["y"]

#     shoulder_tilt = abs(y("leftShoulder") - y("rightShoulder"))
#     hip_tilt = abs(y("leftHip") - y("rightHip"))

#     left_arm = abs(x("leftWrist") - x("leftShoulder"))
#     right_arm = abs(x("rightWrist") - x("rightShoulder"))
#     arm_asymmetry = abs(left_arm - right_arm)

#     shoulder_center = (y("leftShoulder") + y("rightShoulder")) / 2
#     hip_center = (y("leftHip") + y("rightHip")) / 2
#     spine_height = hip_center - shoulder_center

#     spinal_compression = max(0, int(spine_height / 28))
#     posture_collapse = max(0, int(shoulder_tilt / 4))
#     pelvic_tilt_back = max(0, int(hip_tilt / 5))
#     leg_hamstring = max(0, int(arm_asymmetry / 6))

#     return {
#         "max_height_gain_inches": round(min(1.5, spinal_compression * 0.015), 2),
#         "spinal_compression": min(100, spinal_compression),
#         "posture_collapse": min(100, posture_collapse),
#         "pelvic_tilt_back": min(100, pelvic_tilt_back),
#         "leg_hamstring": min(100, leg_hamstring),
#     }


# # =========================================================
# # OPTIMIZATION BREAKDOWN (NO AI MATH)
# # =========================================================
# def build_optimization_breakdown(metrics: dict):
#     MAX_LOSS = {
#         "spinal_compression": 4.0,
#         "posture_collapse": 3.0,
#         "pelvic_tilt_back": 2.5,
#         "leg_hamstring": 3.5,
#     }

#     SCALE = {
#         "spinal_compression": 100,
#         "posture_collapse": 50,
#         "pelvic_tilt_back": 60,
#         "leg_hamstring": 80,
#     }

#     breakdown = {}

#     for key in MAX_LOSS:
#         value = metrics[key]
#         max_loss = MAX_LOSS[key]

#         current_loss = round((value / SCALE[key]) * max_loss, 2)
#         percent_optimized = int(
#             max(0, min(100, 100 - (current_loss / max_loss * 100)))
#         )

#         breakdown[key] = {
#             "current_loss_cm": current_loss,
#             "max_loss_cm": max_loss,
#             "percent_optimized": percent_optimized,
#         }

#     return breakdown


# # =========================================================
# # FULL POSTURE ANALYSIS API (FINAL)
# # =========================================================
# class FullPostureAnalysisAPIView(APIView):
#     parser_classes = [MultiPartParser]
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):

#         front = request.FILES.get("front")
#         side = request.FILES.get("side")
#         back = request.FILES.get("back")
#         t_pose_image = request.FILES.get("t_pose")
#         raw_t_pose_data = request.data.get("t_pose_data")
#         front_data = request.data.get("front_data")
#         side_data = request.data.get("side_data")
#         back_data = request.data.get("back_data")

#         if not all([front, side, back]):
#             return Response(
#                 {"error": "front, side and back images are required"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         # -------------------------------
#         # DEFAULT METRICS
#         # -------------------------------
#         metrics = {
#             "max_height_gain_inches": 0,
#             "spinal_compression": 0,
#             "posture_collapse": 0,
#             "pelvic_tilt_back": 0,
#             "leg_hamstring": 0,
#         }

#         # -------------------------------
#         # T-POSE ANALYSIS
#         # -------------------------------
#         t_pose_data = parse_t_pose_data(raw_t_pose_data)
#         if t_pose_data:
#             try:
#                 metrics = analyze_t_pose_metrics(t_pose_data)
#             except Exception as e:
#                 logger.error(f"T-pose metric error: {e}")

#         optimization_breakdown = build_optimization_breakdown(metrics)

#         # -------------------------------
#         # IMAGE ENCODING
#         # -------------------------------
#         images = [
#             encode_image(front),
#             encode_image(side),
#             encode_image(back),
#         ]
#         if t_pose_image:
#             images.append(encode_image(t_pose_image))

#         # -------------------------------
#         # STRICT PROMPT (LOCKED SCHEMA)
#         # -------------------------------
#         system_prompt = f"""
# You are a professional posture analyst.

# ALL NUMERIC VALUES BELOW ARE FINAL.
# DO NOT modify or recalculate any numbers.

# METRICS:
# {json.dumps(metrics, indent=2)}

# OPTIMIZATION_BREAKDOWN:
# {json.dumps(optimization_breakdown, indent=2)}

# Return JSON in EXACTLY this structure:

# {{
#   "summary": {{
#     "summary": "string",
#     "note": "string",
#     "recommendations": [
#       {{
#         "title": "string",
#         "description": "string"
#       }}
#     ]
#   }}
# }}

# Rules:
# - Do NOT add extra keys
# - Do NOT remove keys
# - Do NOT return flat JSON
# - Do NOT explain outside JSON
# """.strip()

#         # -------------------------------
#         # OPENAI MULTIMODAL CALL
#         # -------------------------------
#         response = client.responses.create(
#             model="gpt-4o",
#             input=[
#                 {"role": "system", "content": system_prompt},
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "input_text", "text": "Analyze posture and suggest improvements."},
#                         *[
#                             {"type": "input_image", "image_url": img}
#                             for img in images
#                         ],
#                     ],
#                 },
#             ],
#             max_output_tokens=800,
#         )

#         ai = safe_json_loads(response.output_text)
#         summary_block = ai.get("summary", {})

#         # -------------------------------
#         # FINAL RESPONSE (SAFE)
#         # -------------------------------
#         final_response = {
#             "analysis": {
#                 "summary": {
#                     "summary": summary_block.get("summary", ""),
#                     "max_height_gain_inches": metrics["max_height_gain_inches"],
#                     "note": summary_block.get("note", ""),
#                     "spinal_compression": metrics["spinal_compression"],
#                     "posture_collapse": metrics["posture_collapse"],
#                     "pelvic_tilt_back": metrics["pelvic_tilt_back"],
#                     "leg_hamstring": metrics["leg_hamstring"],
#                     "recommendations": summary_block.get("recommendations", []),
#                 },
#                 "optimization_breakdown": optimization_breakdown,
#             }
#         }

#         # -------------------------------
#         # SAVE REPORT
#         # -------------------------------
#         PostureReport.objects.create(
#             user=request.user,
#             data=final_response,
#             t_pose_data=t_pose_data,
#         )

#         profile = UserProfile.objects.get(user=request.user)
#         profile.last_scan = timezone.now()
#         profile.save()

#         return Response(final_response, status=status.HTTP_200_OK)


#---------------------------------------------------------------------------------
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import permissions, status

from django.conf import settings
from django.utils import timezone

from .models import PostureReport
from user_profile.models import UserProfile

import base64, json, magic
from openai import OpenAI

from utils.posture_calculations import (
    parse_payload,
    analyze_posture,
    build_optimization_breakdown,
)
from utils.ai_analysis import save_ai_analysis_full_scan

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def encode_image(file):
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    return f"data:{mime};base64,{base64.b64encode(file.read()).decode()}"


def safe_json_loads(txt):
    s, e = txt.find("{"), txt.rfind("}")
    return json.loads(txt[s:e + 1])

def extract_json_request_data(request):
    """
    Removes files and keeps only JSON-safe values
    """
    clean_data = {}

    for key, value in request.data.items():
        if hasattr(value, "read"):  # file object
            continue
        try:
            clean_data[key] = json.loads(value) if isinstance(value, str) else value
        except Exception:
            clean_data[key] = value

    return clean_data

class FullPostureAnalysisAPIView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):

        front = request.FILES.get("front")
        side = request.FILES.get("side")
        back = request.FILES.get("back")
        t_pose = request.FILES.get("t_pose")

        if not all([front, side, back]):
            return Response(
                {"error": "front, side and back images are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ PARSE JSON ONCE (FIX)
        front_data = parse_payload(request.data.get("front_data"))
        side_data  = parse_payload(request.data.get("side_data"))
        back_data  = parse_payload(request.data.get("back_data"))
        t_pose_data = parse_payload(request.data.get("t_pose_data"))

        metrics = analyze_posture(
            front=front_data,
            side=side_data,
            back=back_data,
            t_pose=t_pose_data
        )

        optimization = build_optimization_breakdown(metrics)

        images = [
            encode_image(front),
            encode_image(side),
            encode_image(back),
        ]
        if t_pose:
            images.append(encode_image(t_pose))

        system_prompt = f"""
You are a professional posture analyst.

ALL numeric values are FINAL.
DO NOT modify numbers.

METRICS:
{json.dumps(metrics, indent=2)}

OPTIMIZATION_BREAKDOWN:
{json.dumps(optimization, indent=2)}

Return JSON ONLY:
{{
  "summary": {{
    "summary": "string",
    "note": "string",
    "recommendations": [
      {{"title": "string", "description": "string"}}
    ]
  }}
}}
"""

        response = client.responses.create(
            model="gpt-4o",
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Analyze posture and suggest improvements."},
                        *[{"type": "input_image", "image_url": img} for img in images],
                    ],
                },
            ],
            max_output_tokens=800,
        )

        ai = safe_json_loads(response.output_text)

        final_response = {
            
            "summary": {
                "summary": ai["summary"].get("summary", ""),
                "max_height_gain_inches": metrics["max_height_gain_inches"],
                "note": ai["summary"].get("note", ""),
                "spinal_compression": metrics["spinal_compression"],
                "posture_collapse": metrics["posture_collapse"],
                "pelvic_tilt_back": metrics["pelvic_tilt_back"],
                "leg_hamstring": metrics["leg_hamstring"],
                "recommendations": ai["summary"].get("recommendations", []),
            },
            "optimization_breakdown": optimization,
            
        }
        clean_request_data = extract_json_request_data(request)
        PostureReport.objects.create(
            user=request.user,
            data=final_response,
            t_pose_data=t_pose_data,
            raw_request_data=clean_request_data,
            front_data=front_data,
            side_data=side_data,
            back_data=back_data,
            max_height_gain_inches=metrics["max_height_gain_inches"],
        )
        user_data = save_ai_analysis_full_scan(request.user,final_response)
        profile = UserProfile.objects.get(user=request.user)
        profile.last_scan = timezone.now()
        profile.save()

        return Response(final_response, status=status.HTTP_200_OK)
