# notifications/fcm.py
import json
import requests
from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2 import service_account


def get_access_token():
    credentials = service_account.Credentials.from_service_account_file(
        settings.FIREBASE_SERVICE_ACCOUNT,
        scopes=["https://www.googleapis.com/auth/firebase.messaging"]
    )
    credentials.refresh(Request())
    return credentials.token


def send_push_fcm(device_token: str, title: str, body: str, data: dict = None):
    access_token = get_access_token()
    project_id = settings.FIREBASE_PROJECT_ID

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

    message = {
        "message": {
            "token": device_token,
            "notification": {
                "title": title,
                "body": body,
            },
            "data": data or {}
        }
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; UTF-8",
    }

    response = requests.post(url, headers=headers, data=json.dumps(message))

    if response.status_code == 200:
        return {"success": True, "response": response.json()}
    else:
        return {"success": False, "error": response.text, "status_code": response.status_code}
