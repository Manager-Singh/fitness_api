import cv2
import numpy as np
import mediapipe as mp


class AdvancedPoseDetector:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            enable_segmentation=False,
            min_detection_confidence=0.7
        )

        self.THRESHOLDS = {
            'forward_head_angle': 45,
            'pelvic_tilt_angle': 15,
            'height_loss_neck_factor': 0.47,
            'height_loss_pelvis_factor': 0.32
        }

    def _get_coords(self, landmark):
        return np.array([landmark.x, landmark.y])

    def _calculate_angle(self, a, b, c):
        ba = a - b
        bc = c - b
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        return np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0)))

    def _determine_pose_type(self, landmarks):
        left_eye = landmarks[self.mp_pose.PoseLandmark.LEFT_EYE.value]
        right_eye = landmarks[self.mp_pose.PoseLandmark.RIGHT_EYE.value]
        nose = landmarks[self.mp_pose.PoseLandmark.NOSE.value]
        left_ear = landmarks[self.mp_pose.PoseLandmark.LEFT_EAR.value]
        right_ear = landmarks[self.mp_pose.PoseLandmark.RIGHT_EAR.value]
        left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
        right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]

        # Visibility check
        visibilities = [
            left_eye.visibility, right_eye.visibility,
            left_ear.visibility, right_ear.visibility,
            left_shoulder.visibility, right_shoulder.visibility
        ]
        if sum(v < 0.4 for v in visibilities) >= 4:
            return "unknown"

        x_eye_diff = abs(left_eye.x - right_eye.x)
        shoulder_width = abs(left_shoulder.x - right_shoulder.x)
        ear_diff = abs(left_ear.visibility - right_ear.visibility)

        is_side_profile = (
            x_eye_diff < 0.02 or
            ear_diff > 0.5 or
            shoulder_width < 0.1
        )

        return "side" if is_side_profile else "front"

    def _analyze_front_view(self, landmarks, shape):
        return {"alignment": "ok"}, ["Try shoulder mobility drills"], 85

    def _analyze_side_view(self, landmarks, shape):
        return {"head_position": "forward"}, ["Strengthen neck extensors"], 78

    def _calculate_height_loss(self, landmarks, image_shape, pose_type, user_height_inches):
        h, _ = image_shape[:2]
        height_loss = {
            'total_inches': 0.0,
            'forward_head_inches': 0.0,
            'pelvic_tilt_inches': 0.0,
            'other_inches': 0.0
        }

        try:
            if pose_type == "side":
                try:
                    ear = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_EAR.value])
                    shoulder = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value])
                    hip = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value])
                    knee = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE.value])
                    heel = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_HEEL.value])
                except:
                    ear = self._get_coords(landmarks[self.mp_pose.PoseLandmark.RIGHT_EAR.value])
                    shoulder = self._get_coords(landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value])
                    hip = self._get_coords(landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP.value])
                    knee = self._get_coords(landmarks[self.mp_pose.PoseLandmark.RIGHT_KNEE.value])
                    heel = self._get_coords(landmarks[self.mp_pose.PoseLandmark.RIGHT_HEEL.value])

                current_height_px = abs(ear[1] - heel[1]) * h
                if user_height_inches is None or current_height_px < 1:
                    return height_loss

                neck_angle = self._calculate_angle(ear, shoulder, shoulder + np.array([0.0, 0.01]))
                neck_length_px = np.linalg.norm(ear - shoulder) * h

                if neck_angle > self.THRESHOLDS['forward_head_angle']:
                    forward_loss = (
                        neck_length_px * (1 - np.cos(np.radians(neck_angle))) *
                        self.THRESHOLDS['height_loss_neck_factor'] *
                        user_height_inches / current_height_px
                    )
                    height_loss['forward_head_inches'] = round(forward_loss, 2)

                pelvic_angle = self._calculate_angle(shoulder, hip, knee)
                torso_length_px = np.linalg.norm(shoulder - hip) * h

                if pelvic_angle > self.THRESHOLDS['pelvic_tilt_angle']:
                    pelvic_loss = (
                        torso_length_px * np.sin(np.radians(pelvic_angle - self.THRESHOLDS['pelvic_tilt_angle'])) *
                        self.THRESHOLDS['height_loss_pelvis_factor'] *
                        user_height_inches / current_height_px
                    )
                    height_loss['pelvic_tilt_inches'] = round(pelvic_loss, 2)

                height_loss['total_inches'] = round(
                    height_loss['forward_head_inches'] + height_loss['pelvic_tilt_inches'], 2
                )

            elif pose_type == "front":
                shoulder = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value])
                hip = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value])
                spine_length = abs(shoulder[1] - hip[1]) * h

                if spine_length > 0 and user_height_inches:
                    compression_loss = (spine_length * 0.12 * user_height_inches) / (spine_length * 1.2)
                    height_loss['other_inches'] = round(compression_loss, 2)
                    height_loss['total_inches'] = round(compression_loss, 2)

        except Exception as e:
            print(f"[ERROR] Height loss calculation failed: {e}")

        return height_loss

    def analyze_posture(self, image_path: str, user_height_inches: float = None, expected_pose_type: str = None) -> dict:
        try:
            image = cv2.imread(image_path)
            if image is None:
                return {"error": "Could not read image file"}

            results = self.pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            if not results.pose_landmarks:
                return {"error": "No pose detected"}

            landmarks = results.pose_landmarks.landmark
            detected_pose_type = self._determine_pose_type(landmarks)

            if expected_pose_type and expected_pose_type != detected_pose_type:
                return {
                    "error": "Uploaded type mismatch",
                    "detected_type": detected_pose_type,
                    "expected_type": expected_pose_type,
                    "suggestion": "Ensure your photo matches the selected pose type"
                }

            if detected_pose_type == "front":
                basic_details, recommendations, score = self._analyze_front_view(landmarks, image.shape)
            else:
                basic_details, recommendations, score = self._analyze_side_view(landmarks, image.shape)

            landmark_coords = {
                lm.name: {"x": landmarks[lm.value].x, "y": landmarks[lm.value].y}
                for lm in self.mp_pose.PoseLandmark
            }

            height_loss = self._calculate_height_loss(landmarks, image.shape, detected_pose_type, user_height_inches)

            h, _ = image.shape[:2]
            biomech = {}

            if detected_pose_type == "side":
                ear = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_EAR.value])
                shoulder = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value])
                hip = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value])
                knee = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE.value])
                heel = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_HEEL.value])

                neck_angle = self._calculate_angle(ear, shoulder, shoulder + np.array([0.0, 0.01]))
                pelvic_angle = self._calculate_angle(shoulder, hip, knee)
                neck_len = np.linalg.norm(ear - shoulder) * h
                torso_len = np.linalg.norm(shoulder - hip) * h
                image_height = abs(ear[1] - heel[1]) * h

                biomech = {
                    "neck_angle_degrees": round(neck_angle, 2),
                    "pelvic_tilt_angle_degrees": round(pelvic_angle, 2),
                    "neck_length_pixels": round(neck_len, 2),
                    "torso_length_pixels": round(torso_len, 2),
                    "image_height_pixels": round(image_height, 2)
                }

            elif detected_pose_type == "front":
                shoulder = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value])
                hip = self._get_coords(landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value])
                spine_len = abs(shoulder[1] - hip[1]) * h
                biomech = {
                    "spine_length_pixels": round(spine_len, 2)
                }

            details = {
                "pose_type": detected_pose_type,
                "landmarks": landmark_coords,
                "biomechanics": biomech,
                "height_loss_inches": height_loss
            }
            details.update(basic_details)

            return {
                "pose_type": detected_pose_type,
                "posture_score": score,
                "height_loss_inches": height_loss,
                "details": details,
                "recommendations": recommendations
            }

        except Exception as e:
            return {"error": f"Posture analysis failed: {str(e)}"}


# Public function to run
pose_analyzer = AdvancedPoseDetector()

def analyze_posture(image_path: str, user_height: float = None, expected_pose_type: str = None) -> dict:
    return pose_analyzer.analyze_posture(image_path, user_height, expected_pose_type)
