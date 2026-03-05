from utils.teen_optimized_height import TeenProfile
from utils.posture.height_helpers import safe_float, safe_int
from utils.posture.posture_utils import compute_posture_potential_cm


def map_userprofile_to_teenprofile(profile, posture_breakdown) -> TeenProfile:
    print('hello\n')
    print(profile)
    return TeenProfile(
        sex=(profile.gender or "male").lower(),

        age_years=safe_int(profile.age),
        age_months=0,

        current_height_cm=safe_float(profile.current_height_cm),
        father_height_cm=safe_float(profile.father_height_cm),
        mother_height_cm=safe_float(profile.mother_height_cm),

        height_change_12m=profile.g_p_height_change or "0-1",
        shoe_pant_growth=profile.g_p_shoe_pant_growth or "stable",
        voice_stage=profile.g_p_voice_stage or "in_between",
        hair_stage=profile.g_p_facial_armpit_hair or "some",
        looks_vs_peers=profile.g_p_looks or "same",
        last_scan=profile.last_scan or None,

        posture_potential_cm=compute_posture_potential_cm(posture_breakdown),
    )
