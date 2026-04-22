import json

from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET


@require_GET
def apple_app_site_association(request):
    """
    Serve iOS Universal Links association file at:
      /.well-known/apple-app-site-association

    Keep the payload minimal; apps/paths are configured in iOS.
    """
    # NOTE: Replace these with your real values (or move to settings/env).
    team_id = "TEAMID"
    bundle_id = "com.yourapp.bundleid"

    payload = {
        "applinks": {
            "apps": [],
            "details": [
                {
                    "appID": f"{team_id}.{bundle_id}",
                    "paths": ["*"],
                }
            ],
        }
    }
    return HttpResponse(json.dumps(payload), content_type="application/json")


@require_GET
def assetlinks(request):
    """
    Serve Android Digital Asset Links at:
      /.well-known/assetlinks.json
    """
    # NOTE: Replace these with your real values (or move to settings/env).
    package_name = "com.yourapp.package"
    sha256 = "AA:BB:CC:DD:EE:FF:..."

    payload = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": package_name,
                "sha256_cert_fingerprints": [sha256],
            },
        }
    ]
    return HttpResponse(json.dumps(payload), content_type="application/json")


@require_GET
def invite_landing(request):
    """
    Web fallback for app invite links:
      /invite?token=...

    If app is installed and Universal Links/App Links are configured, the OS opens the app.
    If not, users land here instead of a Django 404.
    """
    token = (request.GET.get("token") or "").strip()
    if not token:
        return HttpResponse("Missing invite token.", content_type="text/plain", status=400)

    # If you have a web frontend route for invites, redirect there.
    # Otherwise keep a simple landing page.
    return HttpResponse(
        f"Invite token received. Token: {token}\n",
        content_type="text/plain",
        status=200,
    )

