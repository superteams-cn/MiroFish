"""
邮件发送（可插拔）。

- 未配置 settings.smtp_host 时走「开发桩」：把邮件内容打印到日志，便于本地联调，
  不真正发信；
- 配置 SMTP 后自动改走真实发送，业务代码无需改动。
"""

import smtplib
from email.message import EmailMessage

from ..settings import settings
from .logger import get_logger

logger = get_logger("superfish.mailer")


def send_email(to: str, subject: str, body: str) -> None:
    """发送纯文本邮件；开发桩仅打印到日志。任何异常只记录，不向上抛。"""
    if not settings.smtp_host:
        logger.info(
            "[DEV-EMAIL] 未配置 SMTP，邮件未真正发送（开发桩）：\n"
            f"  收件人: {to}\n  主题: {subject}\n  正文:\n{body}"
        )
        return

    try:
        msg = EmailMessage()
        msg["From"] = settings.email_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        logger.info(f"邮件已发送: to={to} subject={subject}")
    except Exception as e:
        logger.error(f"邮件发送失败: to={to} err={e}")
