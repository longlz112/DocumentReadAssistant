from django.db import models
from django.contrib.auth.models import User


class Paper(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='papers')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='papers/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)
    processing_failed = models.BooleanField(default=False)

    # 论文元数据字段
    meta_title = models.CharField(max_length=500, default='无', blank=True)
    meta_authors = models.CharField(max_length=500, default='无', blank=True)
    meta_keywords = models.TextField(default='无', blank=True)
    meta_abstract = models.TextField(default='无', blank=True)
    meta_journal = models.CharField(max_length=500, default='无', blank=True)
    meta_year = models.CharField(max_length=10, default='无', blank=True)
    meta_confirmed = models.BooleanField(default=False)

    # 知识图谱字段
    knowledge_graph_data = models.JSONField(null=True, blank=True)
    # status: '' = 未构建, 'building' = 构建中, 'ready' = 已完成, 'error' = 构建失败
    knowledge_graph_status = models.CharField(max_length=20, default='')

    def __str__(self):
        return self.title


class LLMUsageRecord(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    model_name = models.CharField(max_length=100, default='qwen-plus')
    operation = models.CharField(max_length=100, default='')
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    request_id = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['-created_at']

