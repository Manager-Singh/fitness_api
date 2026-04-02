# utils/scores_summary.py

# import pandas as pd
# from datetime import date, timedelta
# from django.db.models import F
# from nutration.models_log import NutraEntry
# import calendar
# from workouts.models import WorkoutEntry
# from django.db import models
# from utils.age import get_user_age


# def get_user_score_summary(user, mode=None):
#     today = date.today()
#     start_of_week = today - timedelta(days=today.weekday())
#     end_of_week = start_of_week + timedelta(days=6)

#     # Get nutrition entries
#     entries = NutraEntry.objects.filter(session__user=user).annotate(entry_date=F('session__date'))
#     df = pd.DataFrame(entries.values('entry_date', 'score', 'food_id', 'activity_id'))

#     df['entry_date'] = pd.to_datetime(df.get('entry_date', pd.NaT))
#     if 'score' in df:
#         df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0)
#     else:
#         df['score'] = 0.0

#     df['week'] = df['entry_date'].dt.to_period('W').apply(lambda r: r.start_time.date()) if not df.empty else None
#     df['month'] = df['entry_date'].dt.to_period('M').astype(str) if not df.empty else None
#     df['year'] = df['entry_date'].dt.year if not df.empty else None
#     df['is_food'] = df['food_id'].notnull() if 'food_id' in df else False
#     df['is_activity'] = df['activity_id'].notnull() if 'activity_id' in df else False

#     def get_week_label(start_date, base_date):
#         first_day = base_date.replace(day=1)
#         week_number = ((start_date - first_day).days // 7) + 1
#         return f"Week {week_number}"

#     def get_month_label(month_str):
#         year, month = month_str.split("-")
#         return calendar.month_name[int(month)]

#     def summarize(group_df, group_col, label_func=None, base_date=None, default_key=None):
#         if group_df.empty:
#             empty_result = {
#                 group_col: default_key or str(today),
#                 "food_score": 0,
#                 "activity_score": 0,
#                 "total_score": 0,
#                 "posture_gain_cm": 0.0
#             }
#             if label_func:
#                 empty_result["label"] = label_func(default_key or today, base_date) if base_date else label_func(default_key or today)
#             return [empty_result]

#         summary = (
#             group_df
#             .groupby(group_col)
#             .agg(
#                 food_score=('score', lambda x: x[group_df['is_food']].sum()),
#                 activity_score=('score', lambda x: x[group_df['is_activity']].sum())
#             )
#             .reset_index()
#             .sort_values(by=group_col, ascending=False)
#         )
#         summary['workout_score'] = 0  # placeholder, can be merged later
#         summary['total_score'] = summary['food_score'] + summary['activity_score'] + summary['workout_score']
#         summary['posture_gain_cm'] = (summary['total_score'] * 0.001).round(4)
#         if label_func:
#             summary['label'] = summary[group_col].apply(
#                 lambda val: label_func(val, base_date) if base_date else label_func(val)
#             )
#         return summary.to_dict(orient="records")

#     # 🏋️ Get today's workout points
#     workout_points_today = WorkoutEntry.objects.filter(
#         session__user=user,
#         session__date=today
#     ).aggregate(total=models.Sum('points'))['total'] or 0

#     # ➕ Count of exercises done today
#     exercise_count_today = WorkoutEntry.objects.filter(
#         session__user=user,
#         session__date=today
#     ).count()

#     # 🎂 Get user age
#     try:
#         age = get_user_age(user)
#     except Exception:
#         age = 0  # fallback

#     # 🧮 Nutrition summary for today
#     today_summary = summarize(df[df['entry_date'].dt.date == today], 'entry_date', default_key=today)[0]

#     # 💡 Update today's workout score, exercise count, and total
#     today_summary['workout_score'] = workout_points_today
#     today_summary['exercise_count'] = exercise_count_today
#     today_summary['total_score'] = (
#         today_summary.get('food_score', 0)
#         + today_summary.get('activity_score', 0)
#         + workout_points_today
#     )

#     #  Adult logic: gain only if workout done
#     if age >= 21:
#         if workout_points_today > 0:
#             today_summary['posture_gain_cm'] = round(today_summary['total_score'] * 0.001, 4)
#         else:
#             today_summary['posture_gain_cm'] = 0.0
#     else:
#         today_summary['posture_gain_cm'] = round(today_summary['total_score'] * 0.001, 4)

#     if mode == "today_total_score":
#         return today_summary.get("total_score", 0)

#     return {
#         "total_posture_gain": 0.029,
#         "today": today_summary,
#         "week": summarize(
#             df[(df['entry_date'].dt.date >= start_of_week) & (df['entry_date'].dt.date <= end_of_week)],
#             'week',
#             label_func=get_week_label,
#             base_date=today,
#             default_key=start_of_week
#         ),
#         "month": summarize(
#             df[df['entry_date'].dt.month == today.month],
#             'week',
#             label_func=get_week_label,
#             base_date=today.replace(day=1),
#             default_key=start_of_week
#         ),
#         "year": summarize(
#             df[df['entry_date'].dt.year == today.year],
#             'month',
#             label_func=get_month_label,
#             default_key=today.strftime("%Y-%m")
#         )
#     }



# import pandas as pd
# from datetime import date, timedelta
# from django.db.models import F, Sum
# from nutration.models_log import NutraEntry
# import calendar
# from workouts.models import WorkoutEntry
# from utils.age import get_user_age


# def get_user_score_summary(user, mode=None):
#     today = date.today()
#     start_of_week = today - timedelta(days=today.weekday())
#     end_of_week = start_of_week + timedelta(days=6)

#     # ---------------- Nutrition entries ----------------
#     nutra_entries = NutraEntry.objects.filter(session__user=user).annotate(
#         entry_date=F("session__date")
#     )
#     nutra_df = pd.DataFrame(
#         nutra_entries.values("entry_date", "score", "food_id", "activity_id")
#     )

#     if not nutra_df.empty:
#         nutra_df["entry_date"] = pd.to_datetime(nutra_df["entry_date"], errors="coerce")
#         nutra_df["score"] = pd.to_numeric(nutra_df["score"], errors="coerce").fillna(0)
#         nutra_df["is_food"] = nutra_df["food_id"].notnull()
#         nutra_df["is_activity"] = nutra_df["activity_id"].notnull()
#     else:
#         nutra_df["entry_date"] = pd.to_datetime([])
#         nutra_df["score"] = []
#         nutra_df["is_food"] = []
#         nutra_df["is_activity"] = []

#     # ---------------- Workout entries ----------------
#     workout_entries = WorkoutEntry.objects.filter(session__user=user).annotate(
#         entry_date=F("session__date")
#     )
#     workout_df = pd.DataFrame(workout_entries.values("entry_date", "points"))

#     if not workout_df.empty:
#         workout_df["entry_date"] = pd.to_datetime(workout_df["entry_date"], errors="coerce")
#         workout_df.rename(columns={"points": "workout_score"}, inplace=True)

#     # ---------------- Merge nutrition + workout ----------------
#     if not nutra_df.empty and not workout_df.empty:
#         df = pd.merge(
#             nutra_df,
#             workout_df.groupby("entry_date").agg(workout_score=("workout_score", "sum")).reset_index(),
#             on="entry_date",
#             how="outer",
#         )
#     elif not nutra_df.empty:
#         nutra_df["workout_score"] = 0
#         df = nutra_df
#     elif not workout_df.empty:
#         workout_df["score"] = 0
#         workout_df["is_food"] = False
#         workout_df["is_activity"] = False
#         df = workout_df
#     else:
#         df = pd.DataFrame(columns=["entry_date", "score", "is_food", "is_activity", "workout_score"])

#     # ---------------- Extra cols ----------------
#     if not df.empty:
#         df["week"] = df["entry_date"].dt.to_period("W").apply(lambda r: r.start_time.date())
#         df["month"] = df["entry_date"].dt.to_period("M").astype(str)
#         df["year"] = df["entry_date"].dt.year
#     else:
#         df["week"] = None
#         df["month"] = None
#         df["year"] = None

#     # ---------------- Label helpers ----------------
#     def get_week_label(start_date, base_date):
#         first_day = base_date.replace(day=1)
#         week_number = ((start_date - first_day).days // 7) + 1
#         return f"Week {week_number}"

#     def get_month_label(month_str):
#         year, month = month_str.split("-")
#         return calendar.month_name[int(month)]

#     def summarize(group_df, group_col, label_func=None, base_date=None, default_key=None):
#         if group_df.empty:
#             empty_result = {
#                 group_col: default_key or str(today),
#                 "food_score": 0,
#                 "activity_score": 0,
#                 "workout_score": 0,
#                 "total_score": 0,
#                 "posture_gain_cm": 0.0,
#             }
#             if label_func:
#                 empty_result["label"] = (
#                     label_func(default_key or today, base_date)
#                     if base_date
#                     else label_func(default_key or today)
#                 )
#             return [empty_result]

#         summary = (
#             group_df.groupby(group_col).agg(
#                 food_score=("score", lambda x: x[group_df["is_food"].fillna(False)].sum()),
#                 activity_score=("score", lambda x: x[group_df["is_activity"].fillna(False)].sum()),
#                 workout_score=("workout_score", "sum"),
#             )
#             .reset_index()
#             .sort_values(by=group_col, ascending=False)
#         )

#         summary["total_score"] = (
#             summary["food_score"] + summary["activity_score"] + summary["workout_score"]
#         )
#         summary["posture_gain_cm"] = (summary["total_score"] * 0.001).round(4)

#         if label_func:
#             summary["label"] = summary[group_col].apply(
#                 lambda val: label_func(val, base_date) if base_date else label_func(val)
#             )

#         return summary.to_dict(orient="records")

#     # ---------------- Today's special summary ----------------
#     workout_points_today = workout_entries.filter(session__date=today).aggregate(total=Sum("points"))["total"] or 0
#     exercise_count_today = workout_entries.filter(session__date=today).count()

#     try:
#         age = get_user_age(user)
#     except Exception:
#         age = 0

#     today_summary = summarize(df[df["entry_date"].dt.date == today], "entry_date", default_key=today)[0]
#     today_summary["exercise_count"] = exercise_count_today

#     # adult rule
#     if age >= 21 and workout_points_today == 0:
#         today_summary["posture_gain_cm"] = 0.0

#     if mode == "today_total_score":
#         return today_summary.get("total_score", 0)

#     # ✅ FIX: compute total_posture_gain using summarize instead of df["total_score"]
#     overall_summary = summarize(df, "year")  # dummy grouping to reuse calculation
#     total_posture_gain = sum(item["total_score"] for item in overall_summary) * 0.001

#     return {
#         "total_posture_gain": round(total_posture_gain, 3),
#         "today": today_summary,
#         "week": summarize(
#             df[(df["entry_date"].dt.date >= start_of_week) & (df["entry_date"].dt.date <= end_of_week)],
#             "week",
#             label_func=get_week_label,
#             base_date=today,
#             default_key=start_of_week,
#         ),
#         "month": summarize(
#             df[df["entry_date"].dt.month == today.month],
#             "week",
#             label_func=get_week_label,
#             base_date=today.replace(day=1),
#             default_key=start_of_week,
#         ),
#         "year": summarize(
#             df[df["entry_date"].dt.year == today.year],
#             "month",
#             label_func=get_month_label,
#             default_key=today.strftime("%Y-%m"),
#         ),
#     }



# import pandas as pd
# from datetime import date, timedelta
# from django.db.models import F, Sum
# from nutration.models_log import NutraEntry
# from workouts.models import WorkoutEntry
# import calendar
# from utils.age import get_user_age


# def get_user_score_summary(user, mode=None):
#     today = date.today()
#     start_of_week = today - timedelta(days=today.weekday())
#     end_of_week = start_of_week + timedelta(days=6)

#     # ---------------- Nutrition entries ----------------
#     nutra_entries = NutraEntry.objects.filter(session__user=user).annotate(
#         entry_date=F("session__date")
#     )
#     nutra_df = pd.DataFrame(nutra_entries.values("entry_date", "score", "food_id", "activity_id"))

#     if not nutra_df.empty:
#         nutra_df["entry_date"] = pd.to_datetime(nutra_df["entry_date"], errors="coerce")
#         nutra_df["score"] = pd.to_numeric(nutra_df["score"], errors="coerce").fillna(0)
#         nutra_df["is_food"] = nutra_df["food_id"].notnull()
#         nutra_df["is_activity"] = nutra_df["activity_id"].notnull()
#         nutra_df["food_score"] = nutra_df["score"] * nutra_df["is_food"].astype(int)
#         nutra_df["activity_score"] = nutra_df["score"] * nutra_df["is_activity"].astype(int)
#     else:
#         nutra_df = pd.DataFrame(columns=[
#             "entry_date", "score", "food_id", "activity_id", "is_food", "is_activity", "food_score", "activity_score"
#         ])

#     # ---------------- Workout entries ----------------
#     workout_entries = WorkoutEntry.objects.filter(session__user=user).annotate(
#         entry_date=F("session__date")
#     )
#     workout_df = pd.DataFrame(workout_entries.values("entry_date", "points"))
#     if not workout_df.empty:
#         workout_df["entry_date"] = pd.to_datetime(workout_df["entry_date"], errors="coerce")
#         workout_df.rename(columns={"points": "workout_score"}, inplace=True)
#     else:
#         workout_df = pd.DataFrame(columns=["entry_date", "workout_score"])

#     # ---------------- Merge nutrition + workout ----------------
#     if not nutra_df.empty and not workout_df.empty:
#         workout_sum = workout_df.groupby("entry_date", as_index=False).agg(workout_score=("workout_score", "sum"))
#         df = pd.merge(nutra_df, workout_sum, on="entry_date", how="outer")
#         df["food_score"] = df["food_score"].fillna(0)
#         df["activity_score"] = df["activity_score"].fillna(0)
#         df["workout_score"] = df["workout_score"].fillna(0)
#     elif not nutra_df.empty:
#         nutra_df["workout_score"] = 0
#         df = nutra_df
#     elif not workout_df.empty:
#         workout_df["food_score"] = 0
#         workout_df["activity_score"] = 0
#         df = workout_df
#     else:
#         df = pd.DataFrame(columns=["entry_date", "food_score", "activity_score", "workout_score"])

#     # ---------------- Extra cols ----------------
#     if not df.empty:
#         df["week"] = df["entry_date"].dt.to_period("W").apply(lambda r: r.start_time.date())
#         df["month"] = df["entry_date"].dt.to_period("M").astype(str)
#         df["year"] = df["entry_date"].dt.year

#     # ---------------- Label helpers ----------------
#     def get_week_label(start_date, base_date):
#         first_day = base_date.replace(day=1)
#         week_number = ((start_date - first_day).days // 7) + 1
#         return f"Week {week_number}"

#     def get_month_label(month_str):
#         year, month = month_str.split("-")
#         return calendar.month_name[int(month)]

#     def summarize(group_df, group_col, label_func=None, base_date=None, default_key=None):
#         if group_df.empty:
#             empty_result = {
#                 group_col: default_key or str(today),
#                 "food_score": 0,
#                 "activity_score": 0,
#                 "workout_score": 0,
#                 "total_score": 0,
#                 "posture_gain_cm": 0.0,
#             }
#             if label_func:
#                 empty_result["label"] = (
#                     label_func(default_key or today, base_date) if base_date else label_func(default_key or today)
#                 )
#             return [empty_result]

#         summary = (
#             group_df.groupby(group_col).agg(
#                 food_score=("food_score", "sum"),
#                 activity_score=("activity_score", "sum"),
#                 workout_score=("workout_score", "sum"),
#             )
#             .reset_index()
#             .sort_values(by=group_col, ascending=False)
#         )
#         summary["total_score"] = (summary["food_score"] + summary["activity_score"] + summary["workout_score"]).clip(upper=100)
#         summary["posture_gain_cm"] = (summary["total_score"] * 0.001).round(4)

#         if label_func:
#             summary["label"] = summary[group_col].apply(
#                 lambda val: label_func(val, base_date) if base_date else label_func(val)
#             )

#         return summary.to_dict(orient="records")

#     # ---------------- Today's summary ----------------
#     today_df = df[df["entry_date"].dt.date == today]
#     today_summary = summarize(today_df, "entry_date", default_key=today)[0]

#     today_summary["exercise_count"] = workout_entries.filter(session__date=today).count()

#     try:
#         age = get_user_age(user)
#     except Exception:
#         age = 0

#     if age >= 21 and today_summary["workout_score"] == 0:
#         today_summary["posture_gain_cm"] = 0.0

#     if mode == "today_total_score":
#         return today_summary.get("total_score", 0)

#     overall_summary = summarize(df, "year")
#     total_posture_gain = sum(item["total_score"] for item in overall_summary) * 0.001

#     return {
#         "total_posture_gain": round(total_posture_gain, 3),
#         "today": today_summary,
#         "week": summarize(
#             df[(df["entry_date"].dt.date >= start_of_week) & (df["entry_date"].dt.date <= end_of_week)],
#             "week",
#             label_func=get_week_label,
#             base_date=today,
#             default_key=start_of_week,
#         ),
#         "month": summarize(
#             df[df["entry_date"].dt.month == today.month],
#             "month",
#             label_func=get_month_label,
#             default_key=today.strftime("%Y-%m"),
#         ),
#         "year": summarize(
#             df[df["entry_date"].dt.year == today.year],
#             "month",
#             label_func=get_month_label,
#             default_key=today.strftime("%Y-%m"),
#         ),
#     }





import pandas as pd
from datetime import date, timedelta
from django.db.models import F
from nutration.models_log import NutraEntry
from workouts.models import WorkoutEntry
import calendar
from utils.age import get_user_age


def get_user_score_summary(user, subscription_data, mode=None):
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # ---------------- Nutrition entries ----------------
    nutra_qs = NutraEntry.objects.filter(session__user=user).annotate(entry_date=F("session__date"))
    nutra_df = pd.DataFrame(nutra_qs.values("entry_date", "score", "food_id", "activity_id"))

    if not nutra_df.empty:
        # normalize to midnight (datetime64) so merges/groupbys are consistent
        nutra_df["entry_date"] = pd.to_datetime(nutra_df["entry_date"], errors="coerce").dt.normalize()
        nutra_df["score"] = pd.to_numeric(nutra_df["score"], errors="coerce").fillna(0)
        nutra_df["is_food"] = nutra_df["food_id"].notnull()
        nutra_df["is_activity"] = nutra_df["activity_id"].notnull()
        nutra_df["food_score"] = nutra_df["score"] * nutra_df["is_food"].astype(int)
        nutra_df["activity_score"] = nutra_df["score"] * nutra_df["is_activity"].astype(int)

        # AGGREGATE nutrition by date (important to avoid duplicate workout sums later)
        nutra_agg = (
            nutra_df.groupby("entry_date", as_index=False)
            .agg(food_score=("food_score", "sum"), activity_score=("activity_score", "sum"))
        )
    else:
        nutra_agg = pd.DataFrame(columns=["entry_date", "food_score", "activity_score"])

    # ---------------- Workout entries ----------------
    workout_qs = WorkoutEntry.objects.filter(session__user=user).annotate(entry_date=F("session__date"))
    workout_df = pd.DataFrame(workout_qs.values("entry_date", "points"))

    if not workout_df.empty:
        workout_df["entry_date"] = pd.to_datetime(workout_df["entry_date"], errors="coerce").dt.normalize()
        workout_df.rename(columns={"points": "workout_score"}, inplace=True)
        workout_df["workout_score"] = pd.to_numeric(workout_df["workout_score"], errors="coerce").fillna(0)

        # AGGREGATE workout by date
        workout_agg = (
            workout_df.groupby("entry_date", as_index=False)
            .agg(workout_score=("workout_score", "sum"))
        )
    else:
        workout_agg = pd.DataFrame(columns=["entry_date", "workout_score"])

    # ---------------- Merge aggregated nutrition + aggregated workout ----------------
    if not nutra_agg.empty and not workout_agg.empty:
        df = pd.merge(nutra_agg, workout_agg, on="entry_date", how="outer")
    elif not nutra_agg.empty:
        df = nutra_agg.copy()
        df["workout_score"] = 0
    elif not workout_agg.empty:
        df = workout_agg.copy()
        df["food_score"] = 0
        df["activity_score"] = 0
    else:
        # create typed empty dataframe so .dt accessor won't blow up later
        df = pd.DataFrame({
            "entry_date": pd.to_datetime([], errors="coerce"),
            "food_score": pd.Series(dtype="float"),
            "activity_score": pd.Series(dtype="float"),
            "workout_score": pd.Series(dtype="float"),
        })

    # ensure numeric and no-nulls
    df["food_score"] = pd.to_numeric(df.get("food_score", 0), errors="coerce").fillna(0)
    df["activity_score"] = pd.to_numeric(df.get("activity_score", 0), errors="coerce").fillna(0)
    df["workout_score"] = pd.to_numeric(df.get("workout_score", 0), errors="coerce").fillna(0)

    # ---------------- Extra cols ----------------
    if not df.empty:
        # entry_date is already normalized datetime64[ns]; safe to use .dt
        df["week"] = df["entry_date"].dt.to_period("W").apply(lambda r: r.start_time.date())
        df["month"] = df["entry_date"].dt.to_period("M").astype(str)
        df["year"] = df["entry_date"].dt.year

    # ---------------- Label helpers ----------------
    def get_week_label(start_date, base_date):
        first_day = base_date.replace(day=1)
        week_number = ((start_date - first_day).days // 7) + 1
        return f"Week {week_number}"

    def get_month_label(month_str):
        year, month = month_str.split("-")
        return calendar.month_name[int(month)]

    def summarize(group_df, group_col, label_func=None, base_date=None, default_key=None):
        if group_df.empty:
            empty_result = {
                group_col: default_key or str(today),
                "food_score": 0,
                "activity_score": 0,
                "workout_score": 0,
                "total_score": 0,
                "posture_gain_cm": 0.000,
            }
            if label_func:
                empty_result["label"] = (
                    label_func(default_key or today, base_date) if base_date else label_func(default_key or today)
                )
            return [empty_result]

        summary = (
            group_df.groupby(group_col).agg(
                food_score=("food_score", "sum"),
                activity_score=("activity_score", "sum"),
                workout_score=("workout_score", "sum"),
            )
            .reset_index()
            .sort_values(by=group_col, ascending=False)
        )
        # cap total at 100 per group
        summary["total_score"] = (summary["food_score"] + summary["activity_score"] + summary["workout_score"]).clip(upper=100)
        summary["posture_gain_cm"] = (summary["total_score"] * 0.001).round(4)

        if label_func:
            summary["label"] = summary[group_col].apply(
                lambda val: label_func(val, base_date) if base_date else label_func(val)
            )

        return summary.to_dict(orient="records")

    # ---------------- Today's summary ----------------
    if not df.empty:
        today_df = df[df["entry_date"].dt.date == today]
    else:
        today_df = pd.DataFrame(columns=df.columns)

    today_summary = summarize(today_df, "entry_date", default_key=pd.Timestamp(today))[0]

    # explicit exercise count (number of workout entries today)
    today_summary["exercise_count"] = WorkoutEntry.objects.filter(session__user=user, session__date=today).count()

    try:
        age = get_user_age(user)
    except Exception:
        age = 0

    if age >= 21 and today_summary["workout_score"] == 0:
        today_summary["posture_gain_cm"] = 0.000

    if mode == "today_total_score":
        return today_summary.get("total_score", 0)

    if subscription_data.get("is_trial") and not df.empty:

        trial_start = subscription_data.get("trial_start")
        trial_end = subscription_data.get("trial_end")

        if trial_start and trial_end:
            trial_start = pd.to_datetime(trial_start).normalize()
            trial_end = pd.to_datetime(trial_end).normalize()

            df = df[
                (df["entry_date"] >= trial_start) &
                (df["entry_date"] <= trial_end)
            ]

    # overall_summary = summarize(df, "year")
    # total_posture_gain = sum(item["total_score"] for item in overall_summary) * 0.001
    overall_summary = summarize(df, "year")

    total_score_till_now = sum(
        item.get("total_score", 0) for item in overall_summary
    )

    total_posture_gain = total_score_till_now * 0.001

    return {
        "total_score": int(total_score_till_now),   # ✅ NEW (points till now)
        "total_posture_gain": round(total_posture_gain, 3),
        "today": today_summary,
        "week": summarize(
            df[(df["entry_date"].dt.date >= start_of_week) & (df["entry_date"].dt.date <= end_of_week)],
            "week",
            label_func=get_week_label,
            base_date=today,
            default_key=start_of_week,
        ),
        "month": summarize(
            df[df["entry_date"].dt.month == today.month],
            "month",
            label_func=get_month_label,
            default_key=today.strftime("%Y-%m"),
        ),
        "year": summarize(
            df[df["entry_date"].dt.year == today.year],
            "month",
            label_func=get_month_label,
            default_key=today.strftime("%Y-%m"),
        ),
    }
