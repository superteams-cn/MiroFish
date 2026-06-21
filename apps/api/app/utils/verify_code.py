"""
邮箱验证码（OTP）存储——统一支撑「邮箱验证 / 验证码登录 / 注册 / 找回密码」。

- 6 位数字、带 TTL，存 Redis；key 由调用方按用途拼装（如 verify:{user_id}、
  login:{email}、register:{email}、reset:{email}），本模块统一加前缀 authcode:；
- 一次性消费：校验通过即删除；
- Redis 不可用时存/验都失败（返回 None/False），相关入口需各自降级（如邮箱验证仍有
  链接通道兜底）。
"""

import secrets

from ..core.logger import get_logger
from .rate_limit import get_redis

logger = get_logger("superfish.verify_code")

# 邮箱验证(链接并存)给 30 分钟；登录/注册/重置等即时动作给 10 分钟
TTL_EMAIL_VERIFY = 30 * 60
TTL_AUTH_ACTION = 10 * 60


def _key(scope: str) -> str:
    return f"authcode:{scope}"


def generate_code() -> str:
    """生成 6 位数字验证码（首位可为 0）。"""
    return f"{secrets.randbelow(1_000_000):06d}"


def store_code(scope: str, code: str, ttl: int = TTL_AUTH_ACTION) -> bool:
    """按 scope 写入验证码并设置 TTL。Redis 不可用返回 False。"""
    client = get_redis()
    if client is None:
        return False
    try:
        client.set(_key(scope), code, ex=ttl)
        return True
    except Exception as e:
        logger.warning(f"验证码写入失败 scope={scope}: {e}")
        return False


def verify_code(scope: str, code: str) -> bool:
    """校验验证码：匹配则消费（删除）并返回 True。空码/不匹配/Redis 故障均 False。"""
    code = (code or "").strip()
    if not code:
        return False
    client = get_redis()
    if client is None:
        return False
    try:
        stored = client.get(_key(scope))
        if stored is None:
            return False
        stored_str = stored.decode() if isinstance(stored, bytes) else str(stored)
        if secrets.compare_digest(stored_str, code):
            client.delete(_key(scope))  # 一次性消费
            return True
        return False
    except Exception as e:
        logger.warning(f"验证码校验异常 scope={scope}: {e}")
        return False
