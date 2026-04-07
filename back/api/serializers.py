from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Paper, Note

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class PaperSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paper
        fields = ['id', 'title', 'file', 'uploaded_at', 'is_processed']
        read_only_fields = ['is_processed', 'uploaded_at']

class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ['id', 'paper', 'content', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
