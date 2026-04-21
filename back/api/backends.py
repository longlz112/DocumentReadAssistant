# 让 authenticate 即便遇到 is_active=False 的用户也返回对象，这样就能在视图中区分“密码错误”和“账户禁用”这两种情况
# 需要在 settings 中添加AUTHENTICATION_BACKENDS = ['api.backends.CustomAllowInactiveBackend']

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

UserModel = get_user_model()

class CustomAllowInactiveBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            return None
        if user.check_password(password):
            return user
        return None

    def user_can_authenticate(self, user):
        # 永远允许认证，不管 is_active
        return True