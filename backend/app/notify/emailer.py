"""邮件通知（FR-5）：aiosmtplib + Jinja2 模板（自动转义，修复 1.0 XSS 隐患）。

- 未配置 SMTP 时静默跳过（FR-5.1）；
- 发送失败仅记日志，不重试不阻塞（FR-5.3）。
"""

from email.message import EmailMessage
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.models import Hotspot

log = structlog.get_logger()

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),  # 自动转义
)


def render_hotspot_email(hotspot: Hotspot, keyword: str) -> str:
    template = _jinja.get_template("hotspot.html")
    return template.render(hotspot=hotspot, keyword=keyword)


async def send_hotspot_email(hotspot: Hotspot, keyword: str) -> bool:
    settings = get_settings()
    if not settings.smtp_configured:
        return False  # 静默跳过
    try:
        import aiosmtplib

        msg = EmailMessage()
        msg["From"] = settings.smtp_user
        msg["To"] = settings.mail_to
        msg["Subject"] = f"[{hotspot.importance.upper()}] {hotspot.title[:80]}"
        msg.set_content(f"{hotspot.title}\n{hotspot.url}")  # 纯文本兜底
        msg.add_alternative(render_hotspot_email(hotspot, keyword), subtype="html")

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=True,
        )
        log.info("email_sent", hotspot_id=str(hotspot.id), importance=hotspot.importance)
        return True
    except Exception as e:
        # FR-5.3：失败仅记日志
        log.warning("email_failed", hotspot_id=str(hotspot.id), error=str(e))
        return False
