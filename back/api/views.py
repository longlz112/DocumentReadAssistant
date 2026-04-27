from rest_framework import viewsets, status, views, serializers
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from .models import Paper
from .serializers import PaperSerializer, UserSerializer
from .ai_service import process_paper_to_vector_db, ask_paper_question, analyze_multiple_papers, extract_paper_metadata, build_knowledge_graph
from .mongo import get_sessions_collection
import threading
import uuid
import math
from datetime import datetime, timezone as dt_timezone
from bson import ObjectId
from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
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

    @action(detail=True, methods=['post'], url_path='build_knowledge_graph')
    def build_knowledge_graph_action(self, request, pk=None):
        """触发知识图谱构建（异步）: POST /api/papers/{id}/build_knowledge_graph/"""
        paper = self.get_object()

        if not paper.is_processed:
            return Response({"error": "论文尚未完成解析，请等待解析完成后再构建知识图谱"},
                            status=status.HTTP_400_BAD_REQUEST)

        if paper.knowledge_graph_status == 'building':
            return Response({"message": "知识图谱正在构建中，请稍候"})

        paper.knowledge_graph_status = 'building'
        paper.save(update_fields=['knowledge_graph_status'])

        def graph_task():
            result = build_knowledge_graph(paper.file.path, paper.id)
            if result is not None:
                paper.knowledge_graph_data = result
                paper.knowledge_graph_status = 'ready'
            else:
                paper.knowledge_graph_status = 'error'
            paper.save(update_fields=['knowledge_graph_data', 'knowledge_graph_status'])

        thread = threading.Thread(target=graph_task)
        thread.start()

        return Response({"message": "知识图谱构建已开始，请稍后查询结果"})

    @action(detail=True, methods=['get'], url_path='knowledge_graph')
    def knowledge_graph_data(self, request, pk=None):
        """获取知识图谱数据: GET /api/papers/{id}/knowledge_graph/"""
        paper = self.get_object()
        return Response({
            "status": paper.knowledge_graph_status,
            "data": paper.knowledge_graph_data,
        })


# 用户个人信息接口
class UserProfileView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        data = request.data

        # 修改昵称（first_name）
        if 'nickname' in data:
            user.first_name = data['nickname']

        # 修改邮箱
        if 'email' in data:
            email = data['email']
            if email and User.objects.exclude(pk=user.pk).filter(email=email).exists():
                return Response({"error": "该邮箱已被其他账号使用"}, status=status.HTTP_400_BAD_REQUEST)
            user.email = email

        # 修改密码
        if 'new_password' in data and data['new_password']:
            old_password = data.get('old_password', '')
            if not user.check_password(old_password):
                return Response({"error": "当前密码不正确"}, status=status.HTTP_400_BAD_REQUEST)
            if len(data['new_password']) < 6:
                return Response({"error": "新密码长度不能少于6位"}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(data['new_password'])
            # 密码修改后重新生成 token，使旧 token 失效
            Token.objects.filter(user=user).delete()
            token, _ = Token.objects.get_or_create(user=user)
            user.save()
            return Response({**UserSerializer(user).data, "new_token": token.key, "password_changed": True})

        user.save()
        return Response(UserSerializer(user).data)


# 会话管理接口（使用 MongoDB）
class ChatSessionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    # ── 工具方法 ──────────────────────────────────────────────────

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(dt_timezone.utc).isoformat()

    @staticmethod
    def _serialize(doc: dict, include_messages: bool = True) -> dict:
        """将 MongoDB 文档转为可序列化的 dict。"""
        result = {
            "id": str(doc["_id"]),
            "session_id": doc.get("session_id", ""),
            "title": doc.get("title", "新会话"),
            "session_type": doc.get("session_type", "single"),
            "paper_titles": doc.get("paper_titles", []),
            "created_at": doc.get("created_at", ""),
            "updated_at": doc.get("updated_at", ""),
        }
        if include_messages:
            result["messages"] = doc.get("messages", [])
        else:
            # message_count 由聚合管道注入，非聚合查询时回退计算
            result["message_count"] = doc.get("message_count", len(doc.get("messages", [])))
        return result

    def _get_doc_or_404(self, pk: str, user_id: int) -> dict:
        col = get_sessions_collection()
        try:
            oid = ObjectId(pk)
        except Exception:
            return None
        return col.find_one({"_id": oid, "user_id": user_id})

    # ── CRUD ──────────────────────────────────────────────────────

    def list(self, request):
        """GET /api/sessions/  分页返回当前用户的会话列表（不含 messages，服务端计算消息数）"""
        page = max(int(request.query_params.get("page", 1)), 1)
        page_size = min(int(request.query_params.get("page_size", 10)), 50)

        col = get_sessions_collection()
        match = {"user_id": request.user.id}
        total = col.count_documents(match)
        skip = (page - 1) * page_size

        # 用聚合管道在服务端计算 message_count，避免把 messages 数组传到 Python 再算长度
        docs = list(col.aggregate([
            {"$match": match},
            {"$sort": {"updated_at": -1}},
            {"$skip": skip},
            {"$limit": page_size},
            {"$addFields": {"message_count": {"$size": "$messages"}}},
            {"$project": {"messages": 0}},
        ]))

        return Response({
            "count": total,
            "total_pages": math.ceil(total / page_size) if page_size else 1,
            "page": page,
            "results": [self._serialize(d, include_messages=False) for d in docs],
        })

    def create(self, request):
        """POST /api/sessions/  新建会话"""
        title = (request.data.get("title") or "新会话").strip()[:100]
        session_type = request.data.get("session_type", "single")  # single | multi
        paper_titles = request.data.get("paper_titles", [])
        now = self._now_iso()
        doc = {
            "user_id": request.user.id,
            "session_id": str(uuid.uuid4()),
            "title": title,
            "session_type": session_type,
            "paper_titles": paper_titles,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        result = get_sessions_collection().insert_one(doc)
        doc["_id"] = result.inserted_id
        return Response(self._serialize(doc), status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        """GET /api/sessions/{id}/  会话详情（含 messages）"""
        doc = self._get_doc_or_404(pk, request.user.id)
        if doc is None:
            return Response({"error": "会话不存在"}, status=status.HTTP_404_NOT_FOUND)
        return Response(self._serialize(doc, include_messages=True))

    def partial_update(self, request, pk=None):
        """PATCH /api/sessions/{id}/  修改标题"""
        doc = self._get_doc_or_404(pk, request.user.id)
        if doc is None:
            return Response({"error": "会话不存在"}, status=status.HTTP_404_NOT_FOUND)

        update = {}
        if "title" in request.data:
            update["title"] = (request.data["title"] or "新会话").strip()[:100]
        if not update:
            return Response({"error": "没有可更新的字段"}, status=status.HTTP_400_BAD_REQUEST)

        update["updated_at"] = self._now_iso()
        get_sessions_collection().update_one({"_id": doc["_id"]}, {"$set": update})
        doc.update(update)
        return Response(self._serialize(doc, include_messages=False))

    def destroy(self, request, pk=None):
        """DELETE /api/sessions/{id}/"""
        doc = self._get_doc_or_404(pk, request.user.id)
        if doc is None:
            return Response({"error": "会话不存在"}, status=status.HTTP_404_NOT_FOUND)
        get_sessions_collection().delete_one({"_id": doc["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="add_message")
    def add_message(self, request, pk=None):
        """POST /api/sessions/{id}/add_message/  追加一条消息"""
        doc = self._get_doc_or_404(pk, request.user.id)
        if doc is None:
            return Response({"error": "会话不存在"}, status=status.HTTP_404_NOT_FOUND)

        role = request.data.get("role")
        content = (request.data.get("content") or "").strip()

        if role not in ("user", "assistant"):
            return Response({"error": "role 必须为 user 或 assistant"}, status=status.HTTP_400_BAD_REQUEST)
        if not content:
            return Response({"error": "消息内容不能为空"}, status=status.HTTP_400_BAD_REQUEST)

        message = {"role": role, "content": content, "timestamp": self._now_iso()}
        # 多论文分析时 AI 消息可携带检索关键词
        keywords = request.data.get("keywords")
        if keywords and isinstance(keywords, list):
            message["keywords"] = keywords

        set_fields: dict = {"updated_at": self._now_iso()}
        # 首条用户消息自动生成标题
        if role == "user" and doc.get("title") == "新会话" and len(doc.get("messages", [])) == 0:
            set_fields["title"] = content[:20] + ("..." if len(content) > 20 else "")

        col = get_sessions_collection()
        col.update_one(
            {"_id": doc["_id"]},
            {"$push": {"messages": message}, "$set": set_fields},
        )
        updated = col.find_one({"_id": doc["_id"]})
        return Response(self._serialize(updated, include_messages=True))

