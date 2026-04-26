from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Paper

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class PaperSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paper
        fields = [
            'id', 'title', 'file', 'uploaded_at', 'is_processed',
            'meta_title', 'meta_authors', 'meta_keywords', 'meta_abstract',
            'meta_journal', 'meta_year', 'meta_confirmed',
        ]
        read_only_fields = ['is_processed', 'uploaded_at']
