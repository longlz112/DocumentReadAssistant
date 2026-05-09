from django.urls import path
from . import admin_views

urlpatterns = [
    path('auth/login/', admin_views.AdminLoginView.as_view()),
    path('stats/', admin_views.AdminStatsView.as_view()),
    path('users/', admin_views.AdminUsersView.as_view()),
    path('users/<int:user_id>/', admin_views.AdminUserDetailView.as_view()),
    path('papers/', admin_views.AdminPapersView.as_view()),
    path('papers/keywords/', admin_views.AdminKeywordsView.as_view()),
    path('system/', admin_views.AdminSystemView.as_view()),
    path('llm/stats/', admin_views.AdminLLMStatsView.as_view()),
    path('llm/records/', admin_views.AdminLLMRecordsView.as_view()),
]
