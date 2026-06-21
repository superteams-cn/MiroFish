"""
鉴权接口的 Pydantic 模型。

与既有风格一致：必填字段设为可选、在处理器内手动校验并返回本地化 400，
避免 FastAPI 默认抛出结构不同的 422 错误体。
"""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """注册请求体（注册即验证：需带邮箱验证码）。"""

    email: str | None = Field(default=None, description="邮箱，必填")
    password: str | None = Field(default=None, description="密码，必填")
    display_name: str | None = Field(default=None, description="昵称，可选")
    code: str | None = Field(default=None, description="邮箱验证码，必填")


class LoginRequest(BaseModel):
    """登录请求体。"""

    email: str | None = Field(default=None, description="邮箱，必填")
    password: str | None = Field(default=None, description="密码，必填")


class RefreshRequest(BaseModel):
    """刷新 access token 请求体。"""

    refresh_token: str | None = Field(default=None, description="refresh token，必填")


class ForgotPasswordRequest(BaseModel):
    """申请重置密码请求体。"""

    email: str | None = Field(default=None, description="邮箱，必填")


class ResetPasswordRequest(BaseModel):
    """重置密码请求体。"""

    token: str | None = Field(default=None, description="重置令牌，必填")
    new_password: str | None = Field(default=None, description="新密码，必填")


class VerifyEmailRequest(BaseModel):
    """邮箱验证请求体（魔法链接）。"""

    token: str | None = Field(default=None, description="验证令牌，必填")


class VerifyCodeRequest(BaseModel):
    """邮箱验证码请求体（OTP）。"""

    code: str | None = Field(default=None, description="6 位验证码，必填")


class SendCodeRequest(BaseModel):
    """统一发送验证码请求体。"""

    email: str | None = Field(default=None, description="邮箱，必填")
    purpose: str | None = Field(default=None, description="用途：login / register / reset")


class LoginCodeRequest(BaseModel):
    """验证码登录请求体（无密码）。"""

    email: str | None = Field(default=None, description="邮箱，必填")
    code: str | None = Field(default=None, description="6 位验证码，必填")


class ResetPasswordCodeRequest(BaseModel):
    """验证码重置密码请求体。"""

    email: str | None = Field(default=None, description="邮箱，必填")
    code: str | None = Field(default=None, description="6 位验证码，必填")
    new_password: str | None = Field(default=None, description="新密码，必填")
