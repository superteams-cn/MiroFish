"""
鉴权路由（邮箱+密码，纯个人账户，开放注册）。

响应沿用 {"success": ..., "data"/"error": ...} 信封，与前端契约一致。
P0 仅做注册/登录/刷新/获取当前用户；邮箱验证、限流、配额属于 P3 护栏。
"""

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..db import session_scope
from ..db_models import UserRow
from ..deps import get_current_user, use_locale
from ..schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from ..settings import settings
from ..utils.locale import t
from ..utils.logger import get_logger
from ..utils.mailer import send_email
from ..utils.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    hash_password,
    password_fingerprint,
    verify_password,
)

logger = get_logger("superfish.auth")

router = APIRouter(dependencies=[Depends(use_locale)])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LEN = 8


def _error(message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"success": False, "error": message})


def _public_user(user: UserRow) -> dict:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "status": user.status,
        "email_verified": user.email_verified,
        "created_at": user.created_at,
    }


def _issue_tokens(user_id: str) -> dict:
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }


@router.post("/register")
def register(req: RegisterRequest):
    """注册新账户（开放注册）。成功后直接签发令牌并登录。"""
    email = (req.email or "").strip().lower()
    password = req.password or ""

    if not _EMAIL_RE.match(email):
        return _error(t("auth.invalidEmail"), 400)
    if len(password) < _MIN_PASSWORD_LEN:
        return _error(t("auth.passwordTooShort"), 400)

    now = datetime.now().isoformat()
    user_id = "user_" + uuid.uuid4().hex[:16]
    display_name = (req.display_name or "").strip() or email.split("@")[0]

    with session_scope() as session:
        exists = session.query(UserRow).filter(UserRow.email == email).first()
        if exists is not None:
            return _error(t("auth.emailTaken"), 409)
        user = UserRow(
            user_id=user_id,
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            status="active",
            email_verified=False,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.flush()
        data = {"user": _public_user(user), **_issue_tokens(user.user_id)}

    logger.info(f"新用户注册: {email}")
    return {"success": True, "data": data}


@router.post("/login")
def login(req: LoginRequest):
    """邮箱+密码登录。"""
    email = (req.email or "").strip().lower()
    password = req.password or ""
    if not email or not password:
        return _error(t("auth.missingCredentials"), 400)

    with session_scope() as session:
        user = session.query(UserRow).filter(UserRow.email == email).first()
        # 无论用户是否存在都走一次校验，降低用户枚举差异（错误信息保持一致）
        ok = user is not None and verify_password(password, user.password_hash)
        if not ok:
            return _error(t("auth.invalidCredentials"), 401)
        if user.status != "active":
            return _error(t("auth.accountDisabled"), 403)
        data = {"user": _public_user(user), **_issue_tokens(user.user_id)}

    return {"success": True, "data": data}


@router.post("/refresh")
def refresh(req: RefreshRequest):
    """用 refresh token 换发新的 access/refresh token。"""
    token = (req.refresh_token or "").strip()
    if not token:
        return _error(t("auth.missingRefreshToken"), 400)
    try:
        payload = decode_token(token, expected_type="refresh")
    except Exception:
        return _error(t("auth.invalidToken"), 401)

    user_id = payload.get("sub")
    with session_scope() as session:
        user = session.get(UserRow, user_id)
        if user is None or user.status != "active":
            return _error(t("auth.invalidToken"), 401)
        data = _issue_tokens(user.user_id)

    return {"success": True, "data": data}


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    """申请重置密码：向邮箱发送重置链接。

    无论邮箱是否存在都返回成功，避免用户枚举。开发桩下邮件打印到后端日志。
    """
    email = (req.email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        return _error(t("auth.invalidEmail"), 400)

    with session_scope() as session:
        user = session.query(UserRow).filter(UserRow.email == email).first()
        if user is not None and user.status == "active":
            token = create_reset_token(user.user_id, user.password_hash)
            link = f"{settings.web_base_url}/reset-password?token={token}"
            send_email(
                user.email,
                t("auth.resetEmailSubject"),
                t("auth.resetEmailBody", link=link),
            )
            logger.info(f"已发送重置密码邮件: {email}")

    return {"success": True, "data": {"message": t("auth.resetEmailSent")}}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    """凭重置令牌设置新密码。令牌过期/被改密失效/格式错均返回 400。"""
    token = (req.token or "").strip()
    new_password = req.new_password or ""
    if not token:
        return _error(t("auth.invalidResetToken"), 400)
    if len(new_password) < _MIN_PASSWORD_LEN:
        return _error(t("auth.passwordTooShort"), 400)

    try:
        payload = decode_token(token, expected_type="reset")
    except Exception:
        return _error(t("auth.invalidResetToken"), 400)

    with session_scope() as session:
        user = session.get(UserRow, payload.get("sub"))
        # 指纹不符 = 密码已改过（旧链接） → 失效
        if (
            user is None
            or user.status != "active"
            or payload.get("pwf") != password_fingerprint(user.password_hash)
        ):
            return _error(t("auth.invalidResetToken"), 400)
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now().isoformat()

    logger.info(f"密码已重置: user={payload.get('sub')}")
    return {"success": True, "data": {"message": t("auth.resetSuccess")}}


@router.get("/me")
def me(current=Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return {"success": True, "data": current}
