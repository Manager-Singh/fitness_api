# core/admin_site.py
from django.contrib.admin import AdminSite
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token       # if you use DRF tokens

class FitnessAdmin(AdminSite):
    site_header  = "🏋️ Fitness App Admin"
    site_title   = "Fitness Admin"
    index_title  = "Dashboard"

    # Hide unwanted apps/models in the sidebar
    HIDDEN_APPS  = {"admin_interface", "authtoken"}     # by app label
    HIDDEN_MODELS = {Group, Token}                      # by class

    def get_app_list(self, request):
        app_list = super().get_app_list(request)
        # strip unwanted apps
        app_list = [app for app in app_list
                    if app["app_label"] not in self.HIDDEN_APPS]
        # strip unwanted models per app
        for app in app_list:
            app["models"] = [m for m in app["models"]
                             if m["model"] not in self.HIDDEN_MODELS]
        return app_list

admin_site = FitnessAdmin(name="fitness_admin")
