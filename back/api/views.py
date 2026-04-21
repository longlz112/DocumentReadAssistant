from rest_framework import viewsets, status, views, serializers
from rest_framework.decorators import action
from .models import Paper, Note
from .serializers import PaperSerializer, NoteSerializer
from .ai_service import process_paper_to_vector_db, ask_paper_question
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

#
# class NoteViewSet(viewsets.ModelViewSet):
#     serializer_class = NoteSerializer
#
#     def get_queryset(self):
#         # 可以按论文ID过滤笔记: GET /api/notes/?paper_id=1
#         queryset = Note.objects.filter(user=self.request.user).order_by('-updated_at')
#         paper_id = self.request.query_params.get('paper_id')
#         if paper_id:
#             queryset = queryset.filter(paper_id=paper_id)
#         return queryset
#
#     def perform_create(self, serializer):
#         serializer.save(user=self.request.user)
#
#
