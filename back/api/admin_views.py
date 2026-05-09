import re
import sys
from datetime import timedelta

import psutil
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status, views
from rest_framework.authtoken.models import Token
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from .models import LLMUsageRecord, Paper


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class AdminLoginView(views.APIView):
    permission_classes = []

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        user = authenticate(username=username, password=password)
        if user is None:
            return Response({'error': '用户名或密码错误'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_staff:
            return Response({'error': '无管理员权限'}, status=status.HTTP_403_FORBIDDEN)
        if not user.is_active:
            return Response({'error': '账号已被禁用'}, status=status.HTTP_403_FORBIDDEN)
        token, _ = Token.objects.get_or_create(user=user)
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        return Response({
            'token': token.key,
            'username': user.username,
            'is_superuser': user.is_superuser,
        })


class AdminStatsView(views.APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()
        week_ago = timezone.now() - timedelta(days=7)

        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        today_new_users = User.objects.filter(date_joined__date=today).count()
        recently_active = User.objects.filter(last_login__gte=week_ago).count()

        total_papers = Paper.objects.count()
        today_new_papers = Paper.objects.filter(uploaded_at__date=today).count()
        processed_papers = Paper.objects.filter(is_processed=True).count()

        user_growth = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            user_growth.append({
                'date': day.strftime('%m-%d'),
                'count': User.objects.filter(date_joined__date=day).count(),
            })

        paper_trend = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            paper_trend.append({
                'date': day.strftime('%m-%d'),
                'count': Paper.objects.filter(uploaded_at__date=day).count(),
            })

        return Response({
            'users': {
                'total': total_users,
                'active': active_users,
                'today_new': today_new_users,
                'recently_active': recently_active,
            },
            'papers': {
                'total': total_papers,
                'today_new': today_new_papers,
                'processed': processed_papers,
                'pending': total_papers - processed_papers,
            },
            'user_growth': user_growth,
            'paper_trend': paper_trend,
        })


class AdminUsersView(views.APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        search = request.query_params.get('search', '')
        is_active = request.query_params.get('is_active', '')
        is_staff = request.query_params.get('is_staff', '')
        page = max(int(request.query_params.get('page', 1)), 1)
        page_size = min(int(request.query_params.get('page_size', 20)), 100)

        qs = User.objects.all().order_by('-date_joined')
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))
        if is_active in ('true', 'false'):
            qs = qs.filter(is_active=(is_active == 'true'))
        if is_staff in ('true', 'false'):
            qs = qs.filter(is_staff=(is_staff == 'true'))

        total = qs.count()
        users = qs[(page - 1) * page_size: page * page_size]
        data = [
            {
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'first_name': u.first_name,
                'is_active': u.is_active,
                'is_staff': u.is_staff,
                'is_superuser': u.is_superuser,
                'date_joined': u.date_joined.isoformat() if u.date_joined else None,
                'last_login': u.last_login.isoformat() if u.last_login else None,
                'paper_count': u.papers.count(),
            }
            for u in users
        ]
        return Response({'total': total, 'results': data})


class AdminUserDetailView(views.APIView):
    permission_classes = [IsAdminUser]

    def put(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
        if user.is_superuser and not request.user.is_superuser:
            return Response({'error': '无权修改超级管理员'}, status=status.HTTP_403_FORBIDDEN)
        if user.pk == request.user.pk:
            return Response({'error': '不能修改自己的状态'}, status=status.HTTP_400_BAD_REQUEST)
        if 'is_active' in request.data:
            user.is_active = bool(request.data['is_active'])
        if 'is_staff' in request.data:
            user.is_staff = bool(request.data['is_staff'])
        user.save()
        return Response({
            'id': user.id,
            'username': user.username,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
        })


class AdminPapersView(views.APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        search = request.query_params.get('search', '')
        is_processed = request.query_params.get('is_processed', '')
        meta_confirmed = request.query_params.get('meta_confirmed', '')
        year = request.query_params.get('year', '')
        page = max(int(request.query_params.get('page', 1)), 1)
        page_size = min(int(request.query_params.get('page_size', 20)), 100)

        qs = Paper.objects.select_related('user').order_by('-uploaded_at')
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(meta_title__icontains=search)
                | Q(meta_authors__icontains=search)
                | Q(meta_keywords__icontains=search)
            )
        if is_processed in ('true', 'false'):
            qs = qs.filter(is_processed=(is_processed == 'true'))
        if meta_confirmed in ('true', 'false'):
            qs = qs.filter(meta_confirmed=(meta_confirmed == 'true'))
        if year:
            qs = qs.filter(meta_year=year)

        total = qs.count()
        papers = qs[(page - 1) * page_size: page * page_size]
        data = [
            {
                'id': p.id,
                'title': p.title,
                'meta_title': p.meta_title,
                'meta_authors': p.meta_authors,
                'meta_keywords': p.meta_keywords,
                'meta_journal': p.meta_journal,
                'meta_year': p.meta_year,
                'is_processed': p.is_processed,
                'meta_confirmed': p.meta_confirmed,
                'uploaded_at': p.uploaded_at.isoformat() if p.uploaded_at else None,
                'username': p.user.username,
            }
            for p in papers
        ]
        return Response({'total': total, 'results': data})

    def patch(self, request):
        paper_ids = request.data.get('ids', [])
        action = request.data.get('action')
        if not paper_ids:
            return Response({'error': '未指定论文'}, status=status.HTTP_400_BAD_REQUEST)
        papers = Paper.objects.filter(id__in=paper_ids)
        if action == 'confirm_meta':
            papers.update(meta_confirmed=True)
        elif action == 'mark_processed':
            papers.update(is_processed=True)
        else:
            return Response({'error': '未知操作'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'updated': papers.count()})


class AdminKeywordsView(views.APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        keyword_freq = {}
        for kw_str in Paper.objects.exclude(meta_keywords='无').values_list('meta_keywords', flat=True):
            if not kw_str or kw_str == '无':
                continue
            for kw in re.split(r'[,;，；、\n]+', kw_str):
                kw = kw.strip()
                if kw and len(kw) > 1:
                    keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
        sorted_kws = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:50]
        return Response([{'keyword': k, 'count': v} for k, v in sorted_kws])


class AdminSystemView(views.APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk_path = 'C:\\' if sys.platform == 'win32' else '/'
        disk = psutil.disk_usage(disk_path)
        net = psutil.net_io_counters()
        return Response({
            'cpu': {'percent': cpu_percent, 'count': psutil.cpu_count()},
            'memory': {
                'total': mem.total,
                'used': mem.used,
                'available': mem.available,
                'percent': mem.percent,
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent,
            },
            'network': {
                'bytes_sent': net.bytes_sent,
                'bytes_recv': net.bytes_recv,
            },
        })


class AdminLLMStatsView(views.APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()
        daily_limit = 100000

        overall = LLMUsageRecord.objects.aggregate(
            calls=Count('id'),
            input=Sum('input_tokens'),
            output=Sum('output_tokens'),
            total=Sum('total_tokens'),
        )
        today_stats = LLMUsageRecord.objects.filter(created_at__date=today).aggregate(
            calls=Count('id'),
            total=Sum('total_tokens'),
        )
        today_total = today_stats.get('total') or 0

        trend = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            d = LLMUsageRecord.objects.filter(created_at__date=day).aggregate(
                total=Sum('total_tokens'), calls=Count('id')
            )
            trend.append({
                'date': day.strftime('%m-%d'),
                'total_tokens': d['total'] or 0,
                'calls': d['calls'] or 0,
            })

        op_dist = list(
            LLMUsageRecord.objects.values('operation')
            .annotate(calls=Count('id'), total=Sum('total_tokens'))
            .order_by('-calls')[:10]
        )

        return Response({
            'overall': {
                'calls': overall.get('calls') or 0,
                'input_tokens': overall.get('input') or 0,
                'output_tokens': overall.get('output') or 0,
                'total_tokens': overall.get('total') or 0,
            },
            'today': {
                'calls': today_stats.get('calls') or 0,
                'total_tokens': today_total,
                'alert': today_total > daily_limit,
                'daily_limit': daily_limit,
            },
            'trend': trend,
            'op_distribution': op_dist,
        })


class AdminLLMRecordsView(views.APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        page = max(int(request.query_params.get('page', 1)), 1)
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        qs = LLMUsageRecord.objects.order_by('-created_at')
        total = qs.count()
        records = qs[(page - 1) * page_size: page * page_size]
        data = [
            {
                'id': r.id,
                'created_at': r.created_at.isoformat(),
                'model_name': r.model_name,
                'operation': r.operation,
                'input_tokens': r.input_tokens,
                'output_tokens': r.output_tokens,
                'total_tokens': r.total_tokens,
                'request_id': r.request_id,
            }
            for r in records
        ]
        return Response({'total': total, 'results': data})
