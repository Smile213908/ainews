"""运行时配置（pydantic-settings）。

安全规则（PRD §6 / 技术选型 §8.2）：
- API_KEYS 为必填项，缺失时启动直接报错并列出缺失字段，不做静默降级；
- AI / SMTP / Twitter 等外部服务凭据为可选项，缺失时对应能力走文档定义的降级行为
  （R-207、FR-5.1），不阻塞主流程。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 必填：逗号分隔的 API Key 列表。缺失即启动失败（FR-7.1）。
    api_keys: str

    database_url: str = "sqlite:///./dev.db"
    redis_url: str = "redis://localhost:6379/0"

    # AI（OpenAI 兼容接口）：base_url + key + model 三元组，M2 流水线使用。
    # 默认接 OpenAI 官方；换 DeepSeek/通义/OpenRouter/自建 vLLM 只改这三个变量。
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str | None = None
    ai_model: str = "gpt-4o-mini"

    # Twitter 第三方 API（twitterapi.io）
    twitter_api_key: str | None = None

    # SMTP 邮件通知
    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_user: str | None = None
    smtp_password: str | None = None
    mail_to: str | None = None

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.mail_to)


@lru_cache
def get_settings() -> Settings:
    # 缺少必填项时 pydantic 抛出 ValidationError，错误信息列出缺失字段——
    # 正是 PRD 要求的"启动校验缺失即明确报错"。
    return Settings()  # type: ignore[call-arg]
