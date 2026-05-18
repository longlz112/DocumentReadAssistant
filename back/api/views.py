import json
from rest_framework import viewsets, status, views, serializers
from rest_framework.decorators import action
from .models import Paper, OperationLog
from .serializers import PaperSerializer, UserSerializer
from .ai_service import (
    process_paper_to_vector_db, ask_paper_question, ask_paper_question_stream,
    analyze_multiple_papers, analyze_multiple_papers_stream,
    extract_paper_metadata, build_knowledge_graph, _thread_local,
)
from .mongo import get_sessions_collection
import threading
import uuid
import math
import os
import shutil
from datetime import datetime, timezone as dt_timezone
from bson import ObjectId
from django.utils import timezone
from django.contrib.auth import authenticate
from django.http import StreamingHttpResponse
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User


def create_operation_log(user, log_info, result='success'):
    """记录用户操作日志（静默失败，不影响主流程）。"""
    try:
        OperationLog.objects.create(
            user=user,
            log_info=log_info,
            operation_result=result,
        )
    except Exception:
        pass


def _load_session_history(session_id, user_id):
    """从 MongoDB 加载会话消息历史。"""
    try:
        col = get_sessions_collection()
        doc = col.find_one({"_id": ObjectId(session_id), "user_id": user_id})
        return doc.get("messages", []) if doc else []
    except Exception:
        return []


# 简单的用户认证接口
class AuthView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        action_type = request.data.get('action', 'login')  # login or register

        if action_type == 'register':
            if User.objects.filter(username=username).exists():
                create_operation_log(None, f"注册失败：用户名 {username} 已存在", 'failed')
                return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.create_user(username=username, password=password)
            token, _ = Token.objects.get_or_create(user=user)
            create_operation_log(user, f"用户注册：{username}", 'success')
            return Response({"token": token.key, "username": user.username})

        elif action_type == 'login':
            user = authenticate(username=username, password=password)

            if user is None:
                create_operation_log(None, f"登录失败：用户名 {username} 密码错误", 'failed')
                return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

            if not user.is_active:
                create_operation_log(user, f"登录失败：账号已禁用 ({username})", 'failed')
                return Response({"error": "Account is disabled"}, status=status.HTTP_403_FORBIDDEN)

            token, _ = Token.objects.get_or_create(user=user)

            res = Response({
                "token": token.key,
                "username": user.username,
                "last_login": user.last_login.isoformat() if user.last_login else None
            })

            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            create_operation_log(user, f"用户登录：{username}", 'success')
            return res


# 论文处理
class PaperViewSet(viewsets.ModelViewSet):
    serializer_class = PaperSerializer

    def get_queryset(self):
        return Paper.objects.filter(user=self.request.user).order_by('-uploaded_at')

    def perform_create(self, serializer):
        title = self.request.data.get('title', 'Untitled')
        print(title)
        if Paper.objects.filter(user=self.request.user, title=title).exists():
            raise serializers.ValidationError({"error": "This paper has already been uploaded."})

        paper = serializer.save(user=self.request.user, title=self.request.data.get('title', 'Untitled'))
        create_operation_log(self.request.user, f"上传论文：{title}", 'success')

        def process_task(p):
            success = process_paper_to_vector_db(p.file.path, p.id)
            if success:
                meta = extract_paper_metadata(p.file.path)
                p.meta_title = meta["title"]
                p.meta_authors = meta["authors"]
                p.meta_keywords = meta["keywords"]
                p.meta_abstract = meta["abstract"]
                p.meta_journal = meta["journal"]
                p.meta_year = meta["year"]
                p.is_processed = True
                p.processing_failed = False
                p.save(update_fields=[
                    'meta_title', 'meta_authors', 'meta_keywords',
                    'meta_abstract', 'meta_journal', 'meta_year',
                    'is_processed', 'processing_failed',
                ])
            else:
                p.processing_failed = True
                p.save(update_fields=['processing_failed'])

        thread = threading.Thread(target=process_task, args=(paper,))
        thread.start()

    @action(detail=True, methods=['post'])
    def ask(self, request, pk=None):
        """问答接口: POST /api/papers/{id}/ask/"""
        paper = self.get_object()
        question = request.data.get('question')
        session_id = request.data.get('session_id')

        if not question:
            return Response({"error": "Question is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not paper.is_processed:
            return Response({"error": "Paper is still being processed. Please wait."},
                            status=status.HTTP_400_BAD_REQUEST)

        history = _load_session_history(session_id, request.user.id) if session_id else []
        answer = ask_paper_question(paper.id, question, history, paper_abstract=paper.meta_abstract)
        create_operation_log(request.user, f"单论文提问：{paper.title[:30]}，问题：{question[:50]}", 'success')
        return Response({"question": question, "answer": answer})

    @action(detail=True, methods=['post'], url_path='ask_stream')
    def ask_stream(self, request, pk=None):
        """流式问答接口: POST /api/papers/{id}/ask_stream/"""
        paper = self.get_object()
        question = request.data.get('question')
        session_id = request.data.get('session_id')

        if not question:
            return Response({"error": "Question is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not paper.is_processed:
            return Response({"error": "Paper is still being processed. Please wait."},
                            status=status.HTTP_400_BAD_REQUEST)

        history = _load_session_history(session_id, request.user.id) if session_id else []
        create_operation_log(request.user, f"流式提问：{paper.title[:30]}，问题：{question[:50]}", 'success')

        def event_stream():
            try:
                for chunk in ask_paper_question_stream(paper.id, question, history, paper_abstract=paper.meta_abstract):
                    yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream; charset=utf-8')
        response['X-Accel-Buffering'] = 'no'
        response['Cache-Control'] = 'no-cache'
        response['Access-Control-Allow-Origin'] = '*'
        return response

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """查询论文处理状态接口: GET /api/papers/{id}/status/"""
        paper = self.get_object()

        if paper.processing_failed:
            return Response({"status": "error", "message": "论文解析失败，请重新解析。"})
        elif paper.is_processed:
            return Response({"status": "processed", "message": "The paper has been processed."})
        else:
            return Response({"status": "processing", "message": "The paper is still being processed."})

    @action(detail=True, methods=['post'], url_path='reparse')
    def reparse(self, request, pk=None):
        """重新解析论文: POST /api/papers/{id}/reparse/"""
        paper = self.get_object()

        if paper.is_processed:
            return Response({"error": "论文已成功解析，无需重新解析。"}, status=status.HTTP_400_BAD_REQUEST)
        if not paper.processing_failed:
            return Response({"error": "论文正在解析中，请稍候。"}, status=status.HTTP_400_BAD_REQUEST)

        paper.processing_failed = False
        paper.save(update_fields=['processing_failed'])

        def process_task(p):
            success = process_paper_to_vector_db(p.file.path, p.id)
            if success:
                meta = extract_paper_metadata(p.file.path)
                p.meta_title = meta["title"]
                p.meta_authors = meta["authors"]
                p.meta_keywords = meta["keywords"]
                p.meta_abstract = meta["abstract"]
                p.meta_journal = meta["journal"]
                p.meta_year = meta["year"]
                p.is_processed = True
                p.processing_failed = False
                p.save(update_fields=[
                    'meta_title', 'meta_authors', 'meta_keywords',
                    'meta_abstract', 'meta_journal', 'meta_year',
                    'is_processed', 'processing_failed',
                ])
            else:
                p.processing_failed = True
                p.save(update_fields=['processing_failed'])

        thread = threading.Thread(target=process_task, args=(paper,))
        thread.start()
        return Response({"message": "已重新开始解析，请稍候。"})

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
        session_id = request.data.get('session_id')

        if len(paper_ids) < 2:
            return Response({"error": "请至少选择两篇论文"}, status=status.HTTP_400_BAD_REQUEST)
        if not question:
            return Response({"error": "问题不能为空"}, status=status.HTTP_400_BAD_REQUEST)

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
            p.id: {"title": p.meta_title, "abstract": p.meta_abstract, "keywords": p.meta_keywords}
            for p in papers
        }
        history = _load_session_history(session_id, request.user.id) if session_id else []
        result = analyze_multiple_papers(paper_ids_titles, question, paper_metadata, history)
        create_operation_log(request.user, f"多论文分析，问题：{question[:50]}", 'success')
        return Response({"question": question, **result})

    @action(detail=False, methods=['post'], url_path='analyze_multi_stream')
    def analyze_multi_stream(self, request):
        """多论文对比分析流式接口: POST /api/papers/analyze_multi_stream/"""
        paper_ids = request.data.get('paper_ids', [])
        question = request.data.get('question', '').strip()
        session_id = request.data.get('session_id')

        if len(paper_ids) < 2:
            return Response({"error": "请至少选择两篇论文"}, status=status.HTTP_400_BAD_REQUEST)
        if not question:
            return Response({"error": "问题不能为空"}, status=status.HTTP_400_BAD_REQUEST)

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
            p.id: {"title": p.meta_title, "abstract": p.meta_abstract, "keywords": p.meta_keywords}
            for p in papers
        }
        history = _load_session_history(session_id, request.user.id) if session_id else []
        create_operation_log(request.user, f"流式多论文分析，问题：{question[:50]}", 'success')

        def event_stream():
            try:
                for chunk in analyze_multiple_papers_stream(paper_ids_titles, question, paper_metadata, history):
                    yield f"data: {chunk}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream; charset=utf-8')
        response['X-Accel-Buffering'] = 'no'
        response['Cache-Control'] = 'no-cache'
        response['Access-Control-Allow-Origin'] = '*'
        return response

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

    def perform_destroy(self, instance):
        """删除论文时同步清理 PDF 文件和 Chroma 向量库目录"""
        from django.conf import settings
        chroma_path = os.path.join(settings.BASE_DIR, 'chroma_db', f'paper_{instance.id}')
        if os.path.exists(chroma_path):
            shutil.rmtree(chroma_path)
        try:
            if instance.file and os.path.exists(instance.file.path):
                os.remove(instance.file.path)
        except Exception:
            pass
        create_operation_log(self.request.user, f"删除论文：{instance.title}", 'success')
        instance.delete()


# 用户个人信息接口
class UserProfileView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        data = request.data

        if 'nickname' in data:
            user.first_name = data['nickname']

        if 'email' in data:
            email = data['email']
            if email and User.objects.exclude(pk=user.pk).filter(email=email).exists():
                return Response({"error": "该邮箱已被其他账号使用"}, status=status.HTTP_400_BAD_REQUEST)
            user.email = email

        if 'new_password' in data and data['new_password']:
            old_password = data.get('old_password', '')
            if not user.check_password(old_password):
                return Response({"error": "当前密码不正确"}, status=status.HTTP_400_BAD_REQUEST)
            if len(data['new_password']) < 6:
                return Response({"error": "新密码长度不能少于6位"}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(data['new_password'])
            Token.objects.filter(user=user).delete()
            token, _ = Token.objects.get_or_create(user=user)
            user.save()
            return Response({**UserSerializer(user).data, "new_token": token.key, "password_changed": True})

        user.save()
        return Response(UserSerializer(user).data)


# 会话管理接口（使用 MongoDB）
class ChatSessionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(dt_timezone.utc).isoformat()

    @staticmethod
    def _serialize(doc: dict, include_messages: bool = True) -> dict:
        result = {
            "id": str(doc["_id"]),
            "session_id": doc.get("session_id", ""),
            "title": doc.get("title", "新会话"),
            "session_type": doc.get("session_type", "single"),
            "paper_titles": doc.get("paper_titles", []),
            "paper_ids": doc.get("paper_ids", []),
            "created_at": doc.get("created_at", ""),
            "updated_at": doc.get("updated_at", ""),
        }
        if include_messages:
            result["messages"] = doc.get("messages", [])
        else:
            result["message_count"] = doc.get("message_count", len(doc.get("messages", [])))
        return result

    def _get_doc_or_404(self, pk: str, user_id: int) -> dict:
        col = get_sessions_collection()
        try:
            oid = ObjectId(pk)
        except Exception:
            return None
        return col.find_one({"_id": oid, "user_id": user_id})

    def list(self, request):
        """GET /api/sessions/"""
        page = max(int(request.query_params.get("page", 1)), 1)
        page_size = min(int(request.query_params.get("page_size", 10)), 50)

        col = get_sessions_collection()
        match = {"user_id": request.user.id}
        total = col.count_documents(match)
        skip = (page - 1) * page_size

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
        session_type = request.data.get("session_type", "single")
        paper_titles = request.data.get("paper_titles", [])
        paper_ids = request.data.get("paper_ids", [])
        now = self._now_iso()
        doc = {
            "user_id": request.user.id,
            "session_id": str(uuid.uuid4()),
            "title": title,
            "session_type": session_type,
            "paper_titles": paper_titles,
            "paper_ids": paper_ids,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        result = get_sessions_collection().insert_one(doc)
        doc["_id"] = result.inserted_id
        return Response(self._serialize(doc), status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        """GET /api/sessions/{id}/"""
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
        keywords = request.data.get("keywords")
        if keywords and isinstance(keywords, list):
            message["keywords"] = keywords

        set_fields: dict = {"updated_at": self._now_iso()}
        if role == "user" and doc.get("title") == "新会话" and len(doc.get("messages", [])) == 0:
            set_fields["title"] = content[:20] + ("..." if len(content) > 20 else "")

        col = get_sessions_collection()
        col.update_one(
            {"_id": doc["_id"]},
            {"$push": {"messages": message}, "$set": set_fields},
        )
        updated = col.find_one({"_id": doc["_id"]})
        return Response(self._serialize(updated, include_messages=True))
