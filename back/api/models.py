from django.db import models
from django.contrib.auth.models import User


class Paper(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='papers')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='papers/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)

    # 论文元数据字段
    meta_title = models.CharField(max_length=500, default='无', blank=True)
    meta_authors = models.CharField(max_length=500, default='无', blank=True)
    meta_keywords = models.TextField(default='无', blank=True)
    meta_abstract = models.TextField(default='无', blank=True)
    meta_journal = models.CharField(max_length=500, default='无', blank=True)
    meta_year = models.CharField(max_length=10, default='无', blank=True)
    meta_confirmed = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class Note(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Note on {self.paper.title} by {self.user.username}"
