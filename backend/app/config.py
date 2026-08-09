"""运行时配置（pydantic-settings）。

安全规则（PRD §6 / 技术选型 §8.2）：
- API_KEYS 为必填项，缺失时启动直接报错并列出缺失字段，不做静默降级；
- AI / SMTP / Twitter 等外部服务凭据为可选项，缺失时对应能力走文档定义的降级行为
  （R-207、FR-5.1），不阻塞主流程。

数据库 / 缓存配置（双环境）：
- APP_ENV=development（默认）：DATABASE_URL / REDIS_URL 未显式配置时，
  由 DB_* / REDIS_* 组件字段拼装，默认指向 localhost 上 docker compose 启动的
  PostgreSQL 16 + Redis 7（`scripts/dev-deps.ps1` 一键拉起）；
- APP_ENV=production：必须显式提供 DATABASE_URL 与 REDIS_URL，缺失即启动失败，
  杜绝生产误连默认地址；
- DATABASE_URL / REDIS_URL 始终优先，用于连接已有的外部实例（含测试注入 SQLite）。
"""

from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 必填：逗号分隔的 API Key 列表。缺失即启动失败（FR-7.1）。
    api_keys: str

    # 运行环境：development（默认）/ production
    app_env: Literal["development", "production"] = "development"

    # ---- 数据库 / 缓存 ----
    # 显式完整 URL 优先（连接已有实例 / 测试注入）；缺省时由组件字段拼装。
    database_url: str | None = None
    redis_url: str | None = None

    # PostgreSQL 组件（开发环境默认指向 docker compose 的 db 服务）
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "hotmonitor"
    db_password: str = "hotmonitor"
    db_name: str = "hotmonitor"

    # Redis 组件（开发环境默认指向 docker compose 的 redis 服务）
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

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

    @model_validator(mode="after")
    def _assemble_urls(self) -> "Settings":
        if self.app_env == "production" and (not self.database_url or not self.redis_url):
            raise ValueError(
                "生产环境（APP_ENV=production）必须显式配置 DATABASE_URL 与 REDIS_URL，"
                "不允许使用开发默认地址"
            )
        if not self.database_url:
            user = quote_plus(self.db_user)
            password = quote_plus(self.db_password)
            self.database_url = (
                f"postgresql+psycopg://{user}:{password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        if not self.redis_url:
            self.redis_url = (
                f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
            )
        return self

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
