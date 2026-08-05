"""系统接口：健康检查（容器探针用，不鉴权）。"""

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hot-monitor-api", "version": "2.0.0"}
