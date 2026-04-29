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

import logging

import base64, json, magic
from openai import OpenAI
from django.forms.models import model_to_dict
import re
from typing import Any, Dict
import tempfile

from utils.posture_calculations import (
    parse_payload,
    analyze_posture,
    build_optimization_breakdown,
)
from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM, posture_segment_opt_pct
from utils.posture.diagnostics_contract import build_posture_optimization_diagnostics
from utils.check_payment import check_subscription_or_response
from utils.ai_analysis import save_ai_analysis_full_scan
from datetime import timedelta, datetime, date
import uuid
from .utils import analyze_posture as analyze_image_posture
from users.models import HeightLedger, PostureState
from users.spec_runtime import apply_pending_pre_scan_engine1
from utils.age import get_user_age_exact
from utils.age import get_user_age

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _make_json_safe(value):
    """
    Ensure values are JSON-serializable for JSONField storage.
    Converts datetimes/dates to ISO-8601 strings and normalizes common types.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        try:
            return value.isoformat()
        except Exception:
            logger.exception("Failed serializing datetime/date to isoformat", extra={"value_type": type(value).__name__})
            return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_make_json_safe(v) for v in value]
    # Fall back to string to avoid JSON serialization errors (e.g., Decimal, model instances).
    try:
        json.dumps(value)
        return value
    except Exception:
        logger.exception("Value not JSON serializable; stringifying", extra={"value_type": type(value).__name__})
        return str(value)


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

    return _make_json_safe(clean_data)


def _enforce_scan_access(user):
    """
    Section 7 monetization gates:
    - Adult free: initial scan only, no re-scans.
    - Adult paid: re-scan every 7 days.
    - Teen unpaid: first scan only.
    - Teen paid: re-scan every 7 days.
    """
    try:
        age = int(get_user_age(user) or 0)
    except Exception:
        age = 0
    sub = check_subscription_or_response(user).data
    is_paid = bool(sub.get("is_paid", False))
    profile = UserProfile.objects.filter(user=user).first()
    last_scan = getattr(profile, "last_scan", None)
    days_since_scan = (timezone.now().date() - last_scan.date()).days if last_scan else None

    if age >= 21:
        if not is_paid and last_scan is not None:
            payload = {
                "error": "scan_locked_paywall",
                "message": "Re-scans are locked on free adult plan. Unlock paid plan to continue.",
                "debug": {
                    "tier": "adult",
                    "age": age,
                    "is_paid": is_paid,
                    "last_scan": last_scan.isoformat() if last_scan else None,
                },
            }
            return payload, 403
        if is_paid and last_scan is not None and days_since_scan is not None and days_since_scan < 7:
            return {
                "error": "scan_not_ready",
                "message": f"Re-scan in {max(0, 7 - days_since_scan)} days.",
            }, 429
        return None, None

    # Teens
    if not is_paid:
        if last_scan is not None:
            payload = {
                "error": "scan_locked_paywall",
                "message": "Unlock full Posture+, ultra-accurate True Optimized Height, and unlimited re-scans.",
                "debug": {
                    "tier": "teen",
                    "age": age,
                    "is_paid": is_paid,
                    "last_scan": last_scan.isoformat() if last_scan else None,
                },
            }
            return payload, 403
        return None, None

    if last_scan is not None and days_since_scan is not None and days_since_scan < 7:
        return {
            "error": "scan_not_ready",
            "message": f"Re-scan in {max(0, 7 - days_since_scan)} days.",
        }, 429
    return None, None

class FullPostureAnalysisAPIView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        gate_error, gate_status = _enforce_scan_access(request.user)
        if gate_error:
            return Response(gate_error, status=gate_status)
        front = request.FILES.get("front")
        side = request.FILES.get("side")
        back = request.FILES.get("back")
        t_pose = request.FILES.get("t_pose")

        if not all([front, side, back, t_pose]):
            return Response(
                {"error": "invalid_scan_input", "message": "front, side, back and t_pose images are required."},
                status=422,
            )

        # ✅ PARSE JSON ONCE (FIX)
        front_data = parse_payload(request.data.get("front_data"))
        side_data  = parse_payload(request.data.get("side_data"))
        back_data  = parse_payload(request.data.get("back_data"))
        t_pose_data = parse_payload(request.data.get("t_pose_data"))
        # print("front_data")
        # print(front_data)
        # print("side_data")
        # print(side_data)
        # print("back_data")
        # print(back_data)
        # print("t_pose_data")
        # print(t_pose_data)
        if all([front_data, side_data, back_data, t_pose_data]):
            metrics = analyze_posture(
                front={"landmarks": front_data},
                side={"landmarks": side_data},
                back={"landmarks": back_data},
                t_pose={"landmarks": t_pose_data},
            )
        else:
            try:
                front_res = _analyze_uploaded_image(front)
                side_res = _analyze_uploaded_image(side)
                back_res = _analyze_uploaded_image(back)
                tpose_res = _analyze_uploaded_image(t_pose)
            except Exception:
                return Response({"error": "scan_unavailable"}, status=503)
            image_results = [front_res, side_res, back_res, tpose_res]
            if any(r.get("error") for r in image_results):
                return Response(
                    {"error": "invalid_scan_input", "message": "Unable to detect posture in one or more images."},
                    status=422,
                )
            metrics = _metrics_from_multiview_results(front_res, side_res, back_res, tpose_res)

        optimization = build_optimization_breakdown(metrics)

        images = [
            encode_image(front),
            encode_image(side),
            encode_image(back),
        ]
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
        nuser = request.user
        profile = UserProfile.objects.get(user=nuser)
        profile_dict = model_to_dict(profile)
        subscription_status = check_subscription_or_response(nuser)
        gender = profile_dict["gender"]
        current_age = int(profile_dict.get("age"))

        subscription_data = subscription_status.data
        is_paid = subscription_data.get("is_paid", False)
        # NOTE:
        # Do NOT set `last_scan` early based on request flags.
        # We only mark scans completed after successfully persisting the PostureReport
        # and updating posture state (prevents locking users out after a failed scan).
        subscription_data_safe = _make_json_safe(subscription_data)
        final_response = {
            'user': {
                'id': nuser.id,
                'username': nuser.username,
                'email': nuser.email,
                'gender':gender,
                'age':current_age,
                'is_paid':is_paid,
                'subscription_data': subscription_data_safe
            },
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
            "posture_optimization_diagnostics": build_posture_optimization_diagnostics(
                user=request.user,
                optimization_breakdown=optimization,
                source="ai_scan",
                rescan_days=7,
            ),
            
        }
        final_response_safe = _make_json_safe(final_response)
        clean_request_data = extract_json_request_data(request)
        PostureReport.objects.create(
            user=request.user,
            data=final_response_safe,
            t_pose_data=_make_json_safe(t_pose_data),
            raw_request_data=clean_request_data,
            front_data=_make_json_safe(front_data),
            side_data=_make_json_safe(side_data),
            back_data=_make_json_safe(back_data),
            max_height_gain_inches=metrics["max_height_gain_inches"],
        )
        posture_bars = _scan_breakdown_from_scores(
            metrics["posture_collapse"],
            metrics["pelvic_tilt_back"],
            metrics["leg_hamstring"],
            metrics["spinal_compression"],
        )
        _apply_scan_to_posture_state(request.user, posture_bars)
        user_data = save_ai_analysis_full_scan(request.user, final_response_safe)
        _mark_scan_completed(request.user)

        return Response(final_response_safe, status=status.HTTP_200_OK)


def _scan_breakdown_from_scores(collapse, pelvic, leg_ham, spinal):
    # Section 1.2 — segment Max_Loss from canonical constants.
    max_loss = {
        "spinal": POSTURE_SEGMENT_MAX_LOSS_CM["spinal_compression"],
        "collapse": POSTURE_SEGMENT_MAX_LOSS_CM["posture_collapse"],
        "pelvic": POSTURE_SEGMENT_MAX_LOSS_CM["pelvic_tilt_back"],
        "legs": POSTURE_SEGMENT_MAX_LOSS_CM["leg_hamstring"],
    }
    current = {
        "spinal": round(max_loss["spinal"] * (1 - spinal / 100.0), 2),
        "collapse": round(max_loss["collapse"] * (1 - collapse / 100.0), 2),
        "pelvic": round(max_loss["pelvic"] * (1 - pelvic / 100.0), 2),
        "legs": round(max_loss["legs"] * (1 - leg_ham / 100.0), 2),
    }
    bars = {}
    for key in ("spinal", "collapse", "pelvic", "legs"):
        m = max_loss[key]
        c = max(0.0, min(m, current[key]))
        bars[key] = {
            "current_loss_cm": round(c, 2),
            "opt_pct": posture_segment_opt_pct(c, m),
        }
    return bars


def _validate_mock_scan_inputs(collapse, pelvic, leg_ham, spinal, wingspan_cm, scan_density_result):
    values = [collapse, pelvic, leg_ham, spinal]
    if any(v < 0 or v > 100 for v in values):
        return {"error": "invalid_scan_input", "message": "Scan scores must be between 0 and 100."}, 422
    if wingspan_cm < 100 or wingspan_cm > 250:
        return {"error": "invalid_scan_input", "message": "wingspan_cm must be between 100 and 250."}, 422
    if scan_density_result not in [0, 1, 2]:
        return {"error": "invalid_scan_input", "message": "scan_density_result must be 0, 1, or 2."}, 422
    return None, None


def _mark_scan_completed(user):
    profile = UserProfile.objects.get(user=user)
    profile.last_scan = timezone.now()
    profile.save(update_fields=["last_scan"])
    age_exact = get_user_age_exact(user) or 0.0
    # Section 5.5: 7-day trial is teen-only (13–20) and starts on first scan.
    if 13.0 <= float(age_exact) < 21.0:
        if user.trial_start is None:
            user.trial_start = timezone.now()
        if user.trial_end is None:
            user.trial_end = user.trial_start + timedelta(days=7)
        user.save(update_fields=["trial_start", "trial_end"])
    # v3.3: Apply any pending pre-scan PosturePlus immediately on scan unlock.
    # Safe to call even when no pending rows exist.
    try:
        apply_pending_pre_scan_engine1(user)
    except Exception:
        logger.exception("Failed applying pending_pre_scan engine1 gains after scan completion")


def _apply_scan_to_posture_state(user, posture_bars):
    """
    Section 4.3 re-scan overwrite + regression guard.
    - Always overwrite Current_Loss per segment.
    - First scan can set Total_Recoverable_Loss from scan value.
    - Repeat scans keep total unless regression requires expansion.
    """
    state, _ = PostureState.objects.get_or_create(user=user)
    prev_scan_completed = bool(state.scan_completed)

    spinal_um = int(round(float(posture_bars["spinal"]["current_loss_cm"]) * 10000))
    collapse_um = int(round(float(posture_bars["collapse"]["current_loss_cm"]) * 10000))
    pelvic_um = int(round(float(posture_bars["pelvic"]["current_loss_cm"]) * 10000))
    legs_um = int(round(float(posture_bars["legs"]["current_loss_cm"]) * 10000))
    new_deficit_um = spinal_um + collapse_um + pelvic_um + legs_um

    historical_posture_um = 0
    for row in HeightLedger.objects.filter(user=user, entry_type="daily_compute"):
        try:
            historical_posture_um += int((row.metadata or {}).get("engine1_delta_um", 0))
        except Exception:
            logger.exception(
                "Failed reading engine1_delta_um from HeightLedger.metadata",
                extra={"row_id": getattr(row, "id", None)},
            )
            continue

    if not prev_scan_completed or int(state.total_recoverable_loss_um or 0) <= 0:
        # First scan establishes canonical recoverable ceiling from scan.
        state.total_recoverable_loss_um = new_deficit_um
    else:
        remaining_ceiling_um = int(state.total_recoverable_loss_um or 0) - historical_posture_um
        if new_deficit_um > max(0, remaining_ceiling_um):
            # Regression guard: expand only upward; never decrease.
            state.total_recoverable_loss_um = historical_posture_um + new_deficit_um

    state.spinal_current_loss_um = spinal_um
    state.collapse_current_loss_um = collapse_um
    state.pelvic_current_loss_um = pelvic_um
    state.legs_current_loss_um = legs_um
    state.scan_completed = True
    state.last_scan_at = timezone.now()
    state.save(
        update_fields=[
            "total_recoverable_loss_um",
            "spinal_current_loss_um",
            "collapse_current_loss_um",
            "pelvic_current_loss_um",
            "legs_current_loss_um",
            "scan_completed",
            "last_scan_at",
            "updated_at",
        ]
    )


def _score_from_inches(loss_inches, max_inches=2.0):
    try:
        v = float(loss_inches)
    except Exception:
        v = 0.0
    v = max(0.0, v)
    score = int(round((v / max_inches) * 100))
    return max(0, min(100, score))


def _scan_scores_from_real_result(scan_result):
    posture_score = int(scan_result.get("posture_score", 70))
    posture_score = max(0, min(100, posture_score))
    collapse_score = 100 - posture_score

    height_loss = scan_result.get("height_loss_inches", {}) or {}
    forward_head_inches = float(height_loss.get("forward_head_inches", 0.0) or 0.0)
    pelvic_inches = float(height_loss.get("pelvic_tilt_inches", 0.0) or 0.0)
    other_inches = float(height_loss.get("other_inches", 0.0) or 0.0)
    total_inches = float(height_loss.get("total_inches", 0.0) or 0.0)

    spinal_score = _score_from_inches(max(other_inches, total_inches * 0.6), max_inches=2.2)
    pelvic_score = _score_from_inches(pelvic_inches, max_inches=1.2)
    leg_ham_score = _score_from_inches(total_inches * 0.35, max_inches=0.8)

    return collapse_score, pelvic_score, leg_ham_score, spinal_score


def _analyze_uploaded_image(file_obj):
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as tmp_file:
        for chunk in file_obj.chunks():
            tmp_file.write(chunk)
        tmp_file.flush()
        return analyze_image_posture(tmp_file.name)


def _metrics_from_multiview_results(front_res, side_res, back_res, tpose_res):
    front_c, _, _, _ = _scan_scores_from_real_result(front_res)
    back_c, _, _, _ = _scan_scores_from_real_result(back_res)
    _, side_pelvic, _, side_spinal = _scan_scores_from_real_result(side_res)
    _, _, tpose_legs, _ = _scan_scores_from_real_result(tpose_res)
    collapse = int(round((front_c + back_c) / 2.0))
    return {
        "max_height_gain_inches": round(min(1.5, side_spinal * 0.015), 2),
        "spinal_compression": side_spinal,
        "posture_collapse": collapse,
        "pelvic_tilt_back": side_pelvic,
        "leg_hamstring": tpose_legs,
    }


class MockScanAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        gate_error, gate_status = _enforce_scan_access(request.user)
        if gate_error:
            return Response(gate_error, status=gate_status)
        try:
            collapse = float(request.data.get("collapse_score", 0))
            pelvic = float(request.data.get("pelvic_score", 0))
            leg_ham = float(request.data.get("leg_ham_score", 0))
            spinal = float(request.data.get("spinal_score", 0))
            wingspan_cm = float(request.data.get("wingspan_cm", 0))
            scan_density_result = int(request.data.get("scan_density_result", -1))
        except Exception:
            return Response(
                {"error": "invalid_scan_input", "message": "Scan payload must contain numeric values."},
                status=422,
            )

        error, status_code = _validate_mock_scan_inputs(
            collapse, pelvic, leg_ham, spinal, wingspan_cm, scan_density_result
        )
        if error:
            return Response(error, status=status_code)

        posture_bars = _scan_breakdown_from_scores(collapse, pelvic, leg_ham, spinal)
        total_recoverable_loss_cm = round(sum(v["current_loss_cm"] for v in posture_bars.values()), 2)
        scan_id = str(uuid.uuid4())
        profile = UserProfile.objects.filter(user=request.user).first()
        try:
            current_height_cm = float(getattr(profile, "base_height_cm", None) or getattr(profile, "current_height_cm", 0) or 0)
        except Exception:
            current_height_cm = 0.0

        payload = {
            "scan_id": scan_id,
            "total_recoverable_loss_cm": total_recoverable_loss_cm,
            "target_height_cm": round(current_height_cm + total_recoverable_loss_cm, 2),
            "posture_bars": posture_bars,
            "source": "mock",
            "scan_completed": True,
            # Spec-style aliases (kept alongside snake_case keys for compatibility).
            "Scan_ID": scan_id,
            "Total_Recoverable_Loss_cm": total_recoverable_loss_cm,
            "Target_Height_cm": round(current_height_cm + total_recoverable_loss_cm, 2),
            "Posture_Bars": posture_bars,
            "Scan_Completed": True,
            "posture_optimization_diagnostics": build_posture_optimization_diagnostics(
                user=request.user,
                optimization_breakdown={
                    "spinal_compression": {
                        "current_loss_cm": posture_bars["spinal"]["current_loss_cm"],
                        "max_loss_cm": POSTURE_SEGMENT_MAX_LOSS_CM["spinal_compression"],
                    },
                    "posture_collapse": {
                        "current_loss_cm": posture_bars["collapse"]["current_loss_cm"],
                        "max_loss_cm": POSTURE_SEGMENT_MAX_LOSS_CM["posture_collapse"],
                    },
                    "pelvic_tilt_back": {
                        "current_loss_cm": posture_bars["pelvic"]["current_loss_cm"],
                        "max_loss_cm": POSTURE_SEGMENT_MAX_LOSS_CM["pelvic_tilt_back"],
                    },
                    "leg_hamstring": {
                        "current_loss_cm": posture_bars["legs"]["current_loss_cm"],
                        "max_loss_cm": POSTURE_SEGMENT_MAX_LOSS_CM["leg_hamstring"],
                    },
                },
                source="mock_scan",
                rescan_days=7,
            ),
        }

        PostureReport.objects.create(
            user=request.user,
            data={"mock_scan": payload},
            raw_request_data=extract_json_request_data(request),
        )
        _apply_scan_to_posture_state(request.user, posture_bars)
        _mark_scan_completed(request.user)
        return Response(payload, status=status.HTTP_200_OK)


class ScanAPIView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        gate_error, gate_status = _enforce_scan_access(request.user)
        if gate_error:
            return Response(gate_error, status=gate_status)
        front = request.FILES.get("front")
        side = request.FILES.get("side")
        back = request.FILES.get("back")
        t_pose = request.FILES.get("t_pose")
        if not all([front, side, back, t_pose]):
            return Response(
                {"error": "invalid_scan_input", "message": "front, side, back and t_pose images are required."},
                status=422,
            )

        # Spec contract includes confidence threshold handling.
        confidence = request.data.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except Exception:
                return Response({"error": "invalid_scan_input", "message": "confidence must be float."}, status=422)
            if confidence < 0.4:
                return Response({"error": "scan_unavailable"}, status=503)

        try:
            front_res = _analyze_uploaded_image(front)
            side_res = _analyze_uploaded_image(side)
            back_res = _analyze_uploaded_image(back)
            tpose_res = _analyze_uploaded_image(t_pose)
        except Exception:
            return Response({"error": "scan_unavailable"}, status=503)

        scan_results = [front_res, side_res, back_res, tpose_res]
        if any(r.get("error") for r in scan_results):
            return Response(
                {"error": "invalid_scan_input", "message": "Unable to detect posture in one or more images."},
                status=422,
            )

        metrics = _metrics_from_multiview_results(front_res, side_res, back_res, tpose_res)
        collapse = metrics["posture_collapse"]
        pelvic = metrics["pelvic_tilt_back"]
        leg_ham = metrics["leg_hamstring"]
        spinal = metrics["spinal_compression"]
        posture_bars = _scan_breakdown_from_scores(collapse, pelvic, leg_ham, spinal)
        total_recoverable_loss_cm = round(sum(v["current_loss_cm"] for v in posture_bars.values()), 2)
        profile = UserProfile.objects.filter(user=request.user).first()
        try:
            current_height_cm = float(getattr(profile, "base_height_cm", None) or getattr(profile, "current_height_cm", 0) or 0)
        except Exception:
            current_height_cm = 0.0
        scan_id = str(uuid.uuid4())
        payload = {
            "scan_id": scan_id,
            "total_recoverable_loss_cm": total_recoverable_loss_cm,
            "target_height_cm": round(current_height_cm + total_recoverable_loss_cm, 2),
            "posture_bars": posture_bars,
            "source": "real_scan",
            "scan_completed": True,
            # Spec-style aliases (kept alongside snake_case keys for compatibility).
            "Scan_ID": scan_id,
            "Total_Recoverable_Loss_cm": total_recoverable_loss_cm,
            "Target_Height_cm": round(current_height_cm + total_recoverable_loss_cm, 2),
            "Posture_Bars": posture_bars,
            "Scan_Completed": True,
            "posture_optimization_diagnostics": build_posture_optimization_diagnostics(
                user=request.user,
                optimization_breakdown={
                    "spinal_compression": {
                        "current_loss_cm": posture_bars["spinal"]["current_loss_cm"],
                        "max_loss_cm": POSTURE_SEGMENT_MAX_LOSS_CM["spinal_compression"],
                    },
                    "posture_collapse": {
                        "current_loss_cm": posture_bars["collapse"]["current_loss_cm"],
                        "max_loss_cm": POSTURE_SEGMENT_MAX_LOSS_CM["posture_collapse"],
                    },
                    "pelvic_tilt_back": {
                        "current_loss_cm": posture_bars["pelvic"]["current_loss_cm"],
                        "max_loss_cm": POSTURE_SEGMENT_MAX_LOSS_CM["pelvic_tilt_back"],
                    },
                    "leg_hamstring": {
                        "current_loss_cm": posture_bars["legs"]["current_loss_cm"],
                        "max_loss_cm": POSTURE_SEGMENT_MAX_LOSS_CM["leg_hamstring"],
                    },
                },
                source="real_scan",
                rescan_days=7,
            ),
        }

        PostureReport.objects.create(
            user=request.user,
            data={
                "scan": payload,
                "scan_engine_output": {
                    "front": front_res,
                    "side": side_res,
                    "back": back_res,
                    "t_pose": tpose_res,
                },
            },
            raw_request_data=extract_json_request_data(request),
        )
        _apply_scan_to_posture_state(request.user, posture_bars)
        _mark_scan_completed(request.user)
        return Response(payload, status=status.HTTP_200_OK)
