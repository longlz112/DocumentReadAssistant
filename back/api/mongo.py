"""
MongoDB 连接与集合封装。
使用懒加载单例，避免 Django 启动时立即连接，
只有首次调用 get_sessions_collection() 时才建立连接。
"""
import threading
from django.conf import settings
from pymongo import MongoClient, DESCENDING
from pymongo.collection import Collection

_lock = threading.Lock()
_client: MongoClient | None = None


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_sessions_collection() -> Collection:
    """返回 chat_sessions 集合，并确保索引已创建。"""
    db = _get_client()[settings.MONGODB_DB]
    col = db['chat_sessions']
    # 确保索引存在（幂等操作）
    col.create_index([('user_id', DESCENDING), ('updated_at', DESCENDING)])
    col.create_index('session_id', unique=True)
    return col
