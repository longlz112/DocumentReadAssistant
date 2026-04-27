from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaperViewSet, AuthView, UserProfileView, ChatSessionViewSet

router = DefaultRouter()
router.register(r'papers', PaperViewSet, basename='paper')
router.register(r'sessions', ChatSessionViewSet, basename='session')

urlpatterns = [
    path('auth/', AuthView.as_view(), name='auth'),
    path('user/profile/', UserProfileView.as_view(), name='user-profile'),
    path('', include(router.urls)),
]
