from rest_framework import viewsets, status, views, serializers
from rest_framework.decorators import action
from .models import Paper
from .serializers import PaperSerializer
from .ai_service import process_paper_to_vector_db, ask_paper_question, analyze_multiple_papers, extract_paper_metadata
import threading
from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User


# 简单的用户认证接口
class AuthView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        action_type = request.data.get('action', 'login')  # login or register

        if action_type == 'register':
            if User.objects.filter(username=username).exists():
                return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.create_user(username=username, password=password)
            token, _ = Token.objects.get_or_create(user=user)
            return Response({"token": token.key, "username": user.username})

        elif action_type == 'login':
            user = authenticate(username=username, password=password)

            # 验证用户存在且密码正确
            if user is None:
                return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

            # 新增：检查 is_active 状态
            if not user.is_active:
                return Response({"error": "Account is disabled"}, status=status.HTTP_403_FORBIDDEN)

            token, _ = Token.objects.get_or_create(user=user)

            res = Response({
                "token": token.key,
                "username": user.username,
                "last_login": user.last_login.isoformat() if user.last_login else None
            })

            # 更新最后登录时间
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            return res


# 论文处理
class PaperViewSet(viewsets.ModelViewSet):
    serializer_class = PaperSerializer

    def get_queryset(self):
        # 仅返回当前用户的论文
        return Paper.objects.filter(user=self.request.user).order_by('-uploaded_at')

    def perform_create(self, serializer):

        title = self.request.data.get('title', 'Untitled')
        print(title)
        # 检查论文是否已上传
        if Paper.objects.filter(user=self.request.user, title=title).exists():
            raise serializers.ValidationError({"error": "This paper has already been uploaded."})

        # 1. 保存论文记录
        paper = serializer.save(user=self.request.user, title=self.request.data.get('title', 'Untitled'))

        # 2. 异步处理PDF以防阻塞请求
        def process_task():
            success = process_paper_to_vector_db(paper.file.path, paper.id)
            if success:
                paper.is_processed = True
                paper.save()
            # 提取元数据（不影响 is_processed 状态）
            meta = extract_paper_metadata(paper.file.path)
            paper.meta_title = meta["title"]
            paper.meta_authors = meta["authors"]
            paper.meta_keywords = meta["keywords"]
            paper.meta_abstract = meta["abstract"]
            paper.meta_journal = meta["journal"]
            paper.meta_year = meta["year"]
            paper.save(update_fields=[
                'meta_title', 'meta_authors', 'meta_keywords',
                'meta_abstract', 'meta_journal', 'meta_year',
            ])

        thread = threading.Thread(target=process_task)
        thread.start()

    @action(detail=True, methods=['post'])
    def ask(self, request, pk=None):
        """问答接口: POST /api/papers/{id}/ask/"""
        paper = self.get_object()
        question = request.data.get('question')

        if not question:
            return Response({"error": "Question is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not paper.is_processed:
            return Response({"error": "Paper is still being processed. Please wait."},
                            status=status.HTTP_400_BAD_REQUEST)

        answer = ask_paper_question(paper.id, question)
        return Response({"question": question, "answer": answer})

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """查询论文处理状态接口: GET /api/papers/{id}/status/"""
        paper = self.get_object()

        if paper.is_processed:
            return Response({"status": "processed", "message": "The paper has been processed."})
        else:
            return Response({"status": "processing", "message": "The paper is still being processed."})

    @action(detail=True, methods=['get'])
    def metadata(self, request, pk=None):
        """获取论文元数据: GET /api/papers/{id}/metadata/"""
        paper = self.get_object()
        return Response({
            "id": paper.id,
            "meta_title": paper.meta_title,
            "meta_authors": paper.meta_authors,
            "meta_keywords": paper.meta_keywords,
            "meta_abstract": paper.meta_abstract,
            "meta_journal": paper.meta_journal,
            "meta_year": paper.meta_year,
            "meta_confirmed": paper.meta_confirmed,
        })

    @action(detail=True, methods=['post'], url_path='reextract_metadata')
    def reextract_metadata(self, request, pk=None):
        """重新提取元数据: POST /api/papers/{id}/reextract_metadata/"""
        paper = self.get_object()
        meta = extract_paper_metadata(paper.file.path)
        paper.meta_title = meta["title"]
        paper.meta_authors = meta["authors"]
        paper.meta_keywords = meta["keywords"]
        paper.meta_abstract = meta["abstract"]
        paper.meta_journal = meta["journal"]
        paper.meta_year = meta["year"]
        paper.meta_confirmed = False
        paper.save(update_fields=[
            'meta_title', 'meta_authors', 'meta_keywords',
            'meta_abstract', 'meta_journal', 'meta_year', 'meta_confirmed',
        ])
        return Response({
            "id": paper.id,
            "meta_title": paper.meta_title,
            "meta_authors": paper.meta_authors,
            "meta_keywords": paper.meta_keywords,
            "meta_abstract": paper.meta_abstract,
            "meta_journal": paper.meta_journal,
            "meta_year": paper.meta_year,
            "meta_confirmed": paper.meta_confirmed,
        })

    @action(detail=True, methods=['post'], url_path='update_metadata')
    def update_metadata(self, request, pk=None):
        """手动保存/确认元数据: POST /api/papers/{id}/update_metadata/"""
        paper = self.get_object()
        fields = ['meta_title', 'meta_authors', 'meta_keywords', 'meta_abstract', 'meta_journal', 'meta_year']
        for field in fields:
            if field in request.data:
                setattr(paper, field, request.data[field] or '无')
        paper.meta_confirmed = True
        paper.save(update_fields=fields + ['meta_confirmed'])
        return Response({
            "id": paper.id,
            "meta_title": paper.meta_title,
            "meta_authors": paper.meta_authors,
            "meta_keywords": paper.meta_keywords,
            "meta_abstract": paper.meta_abstract,
            "meta_journal": paper.meta_journal,
            "meta_year": paper.meta_year,
            "meta_confirmed": paper.meta_confirmed,
        })

    @action(detail=False, methods=['post'], url_path='analyze_multi')
    def analyze_multi(self, request):
        """多论文对比分析接口: POST /api/papers/analyze_multi/"""
        paper_ids = request.data.get('paper_ids', [])
        question = request.data.get('question', '').strip()

        if len(paper_ids) < 2:
            return Response({"error": "请至少选择两篇论文"}, status=status.HTTP_400_BAD_REQUEST)
        if not question:
            return Response({"error": "问题不能为空"}, status=status.HTTP_400_BAD_REQUEST)

        # 验证论文属于当前用户且均已处理
        papers = Paper.objects.filter(id__in=paper_ids, user=request.user)
        if papers.count() != len(paper_ids):
            return Response({"error": "部分论文不存在或无权访问"}, status=status.HTTP_400_BAD_REQUEST)

        not_ready = [p.title for p in papers if not p.is_processed]
        if not_ready:
            return Response(
                {"error": f"以下论文尚未完成解析：{', '.join(not_ready)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        paper_ids_titles = [(p.id, p.title) for p in papers]
        paper_metadata = {
            p.id: {
                "title": p.meta_title,
                "abstract": p.meta_abstract,
                "keywords": p.meta_keywords,
            }
            for p in papers
        }
        result = analyze_multiple_papers(paper_ids_titles, question, paper_metadata)
        return Response({"question": question, **result})
