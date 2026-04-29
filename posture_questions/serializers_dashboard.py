from rest_framework import serializers


class DashboardCardSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    value_cm = serializers.FloatField()


class DashboardNewScanSerializer(serializers.Serializer):
    scan_completed = serializers.BooleanField()
    can_scan = serializers.BooleanField()
    scan_message = serializers.CharField(allow_blank=True, allow_null=True)
    rescan_timer_days = serializers.IntegerField(allow_null=True)
    teen_scan_required = serializers.BooleanField()


class DashboardNewTopGraphSerializer(serializers.Serializer):
    cards = DashboardCardSerializer(many=True)
    teen_lines_cm = serializers.DictField(required=False, allow_null=True)
    adult_target_height_cm = serializers.FloatField(required=False, allow_null=True)


class DashboardNewRoutineSerializer(serializers.Serializer):
    cta = serializers.CharField()
    posture_exercises_fraction = serializers.CharField(allow_blank=True, allow_null=True)
    posture_exercises_done = serializers.IntegerField()
    posture_exercises_total = serializers.IntegerField()
    # v3.4 aliases for dynamic CTA buttons (same counts as posture_exercises_* for teens).
    exercises_done = serializers.IntegerField(required=False, allow_null=True)
    total_exercises = serializers.IntegerField(required=False, allow_null=True)
    # Teen: sum of nutrition + lifestyle dots (0–8). Adult: rough food slots 0–4 from nutrition %.
    habits_logged = serializers.IntegerField(required=False, allow_null=True)
    posture_exercises_percent = serializers.IntegerField(required=False, allow_null=True)
    nutrition_percent = serializers.IntegerField(required=False, allow_null=True)
    teen_nutrition_dots = serializers.IntegerField(required=False, allow_null=True)
    teen_lifestyle_dots = serializers.IntegerField(required=False, allow_null=True)
    streak_days = serializers.IntegerField()
    daily_points = serializers.IntegerField()
    rank = serializers.IntegerField(required=False, allow_null=True)


class DashboardNewPostureOptimizationSerializer(serializers.Serializer):
    total_recoverable_loss_cm = serializers.FloatField(allow_null=True)
    total_current_loss_cm = serializers.FloatField(allow_null=True)
    bars_percent = serializers.DictField()
    raw_segments = serializers.DictField()


class DashboardNewCoreSerializer(serializers.Serializer):
    variant = serializers.ChoiceField(choices=["adult", "teen"])
    profile = serializers.DictField(required=False)
    calculation_mode = serializers.CharField(required=False)
    anomalies = serializers.ListField(child=serializers.CharField(), required=False)
    live_metrics = serializers.DictField(required=False)
    target_metrics = serializers.DictField(required=False)
    # Section 5.1b — teen Genetic_Average curve (yellow dot / legend); null for adults.
    genetic_average_cm = serializers.FloatField(required=False, allow_null=True)
    daily_genetic_average_gain_cm = serializers.FloatField(required=False, allow_null=True)
    scan = DashboardNewScanSerializer()
    top_graph = DashboardNewTopGraphSerializer()
    routine_progress = DashboardNewRoutineSerializer()
    posture_optimization = DashboardNewPostureOptimizationSerializer()
    ai_analysis = serializers.DictField(required=False)
    chart_breakdown = serializers.DictField(required=False, allow_null=True)
    subscription = serializers.DictField(required=False)
    trial_data = serializers.DictField(required=False)
    important_data = serializers.DictField(required=False)
    meta = serializers.DictField(required=False)
    debug = serializers.DictField(required=False)


class DashboardNewResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    dashboard = DashboardNewCoreSerializer()
