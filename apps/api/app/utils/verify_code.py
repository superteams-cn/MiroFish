"""
邮箱验证码（OTP）存储——与魔法链接并存的第二验证通道。

- 6 位数字、带 TTL，存 Redis（key=verifycode:{user_id}）；
- 与验证链接(JWT)互为备份：链接走 /verify-email（无需登录），验证码走
  /verify-email-code（凭登录态绑定用户）；
- Redis 不可用时存/验都失败（返回 None/False），此时用户仍可用链接验证（fail-safe）。
"""

import secrets

from .logger import get_logger
from .rate_limit import get_redis

logger = get_logger("superfish.verify_code")

_CODE_TTL_SECONDS = 30 * 60  # 30 分钟，与产品约定一致


def _key(user_id: str) -> str:
    return f"verifycode:{user_id}"


def generate_code() -> str:
    """生成 6 位数字验证码（首位可为 0）。"""
    return f"{secrets.randbelow(1_000_000):06d}"


def store_code(user_id: str, code: str) -> bool:
    """写入验证码并设置 TTL。Redis 不可用返回 False。"""
    client = get_redis()
    if client is None:
        return False
    try:
        client.set(_key(user_id), code, ex=_CODE_TTL_SECONDS)
        return True
    except Exception as e:
        logger.warning(f"验证码写入失败 user={user_id}: {e}")
        return False


def verify_code(user_id: str, code: str) -> bool:
    """校验验证码：匹配则消费（删除）并返回 True。空码/不匹配/Redis 故障均 False。"""
    code = (code or "").strip()
    if not code:
        return False
    client = get_redis()
    if client is None:
        return False
    try:
        stored = client.get(_key(user_id))
        if stored is None:
            return False
        stored_str = stored.decode() if isinstance(stored, bytes) else str(stored)
        if secrets.compare_digest(stored_str, code):
            client.delete(_key(user_id))  # 一次性消费
            return True
        return False
    except Exception as e:
        logger.warning(f"验证码校验异常 user={user_id}: {e}")
        return False
