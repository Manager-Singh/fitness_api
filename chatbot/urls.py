from django.urls import path
from .views import ai_chat,chat_history

urlpatterns = [
    path("chat", ai_chat, name="ai_chat"),
    path("chat-history", chat_history,name="ai_chat_history"),
]
