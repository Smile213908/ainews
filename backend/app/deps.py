"""鉴权依赖（FR-7.1）：全部 API 需携带有效 X-API-Key。

一期为 API Key 校验；二期 JWT（fastapi-users）接入时只需替换本依赖项，
业务路由零改动（技术选型 §8.1）。
"""

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    api_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    if not api_key or api_key not in settings.api_key_list:
        raise HTTPException(status_code=401, detail="无效或缺失的 API Key")
