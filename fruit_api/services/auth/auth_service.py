from dataclasses import dataclass
from typing import Dict

from django.contrib.auth import authenticate
from django.contrib.auth.models import User


class AuthServiceError(Exception):
    pass


class AuthValidationError(AuthServiceError):
    pass


class AuthConflictError(AuthServiceError):
    pass


class AuthCredentialError(AuthServiceError):
    pass


@dataclass
class UserDTO:
    id: int
    username: str
    first_name: str
    email: str

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'username': self.username,
            'first_name': self.first_name,
            'email': self.email,
        }


def user_to_dto(user: User) -> UserDTO:
    return UserDTO(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        email=user.email,
    )


def register_user(username: str, password: str, email: str = '') -> User:
    if not username or not password:
        raise AuthValidationError('用户名和密码不能为空')

    if User.objects.filter(username=username).exists():
        raise AuthConflictError('用户名已存在')

    return User.objects.create_user(username=username, password=password, email=email)


def login_with_credentials(username: str, password: str) -> User:
    if not username or not password:
        raise AuthValidationError('用户名和密码不能为空')

    user = authenticate(username=username, password=password)
    if user is None:
        raise AuthCredentialError('用户名或密码错误')
    return user


def update_profile_fields(user: User, first_name: str = '', email: str = '') -> User:
    first_name = (first_name or '').strip()
    email = (email or '').strip()

    if first_name:
        user.first_name = first_name
    if email:
        user.email = email
    user.save()
    return user


def change_password_for_user(user: User, old_password: str, new_password: str) -> None:
    if not old_password or not new_password:
        raise AuthValidationError('旧密码和新密码不能为空')
    if not user.check_password(old_password):
        raise AuthCredentialError('旧密码错误')
    if len(new_password) < 6:
        raise AuthValidationError('新密码长度至少6位')

    user.set_password(new_password)
    user.save()
