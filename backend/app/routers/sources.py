"""数据源健康（FR-6）：只读 API，供健康面板与外部监控复用。"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import SourceHealth
from app.schemas import SourceHealthRead

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/health", response_model=list[SourceHealthRead])
def sources_health(session: Session = Depends(get_session)) -> list[SourceHealth]:
    return list(session.exec(select(SourceHealth)).all())
