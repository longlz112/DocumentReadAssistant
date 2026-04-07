from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaperViewSet, AuthView

router = DefaultRouter()
router.register(r'papers', PaperViewSet, basename='paper')
# router.register(r'notes', NoteViewSet, basename='note')

urlpatterns = [
    path('auth/', AuthView.as_view(), name='auth'),
    path('', include(router.urls)),
]
