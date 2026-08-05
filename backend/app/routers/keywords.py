"""关键词管理（FR-1）。

- 创建：空文本拒绝、重复返回 409；
- 列表：含每个关键词的热点计数；
- 删除：不级联删除热点，热点保留、关联置空（FR-1.4）。
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from app.db import get_session
from app.models import Hotspot, Keyword
from app.schemas import KeywordCreate, KeywordRead, KeywordUpdate

router = APIRouter(prefix="/keywords", tags=["keywords"])


def _to_read(session: Session, kw: Keyword) -> KeywordRead:
    count = session.exec(
        select(func.count()).select_from(Hotspot).where(Hotspot.keyword_id == kw.id)
    ).one()
    return KeywordRead(
        id=kw.id,
        text=kw.text,
        category=kw.category,
        is_active=kw.is_active,
        created_at=kw.created_at,
        hotspot_count=count,
    )


@router.get("", response_model=list[KeywordRead])
def list_keywords(session: Session = Depends(get_session)) -> list[KeywordRead]:
    kws = session.exec(select(Keyword).order_by(Keyword.created_at.desc())).all()  # type: ignore[attr-defined]
    return [_to_read(session, kw) for kw in kws]


@router.post("", response_model=KeywordRead, status_code=201)
def create_keyword(body: KeywordCreate, session: Session = Depends(get_session)) -> KeywordRead:
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="关键词不能为空")
    exists = session.exec(select(Keyword).where(Keyword.text == text)).first()
    if exists:
        raise HTTPException(status_code=409, detail=f"关键词「{text}」已存在")
    kw = Keyword(text=text, category=body.category)
    session.add(kw)
    session.commit()
    session.refresh(kw)
    return _to_read(session, kw)


@router.put("/{keyword_id}", response_model=KeywordRead)
def update_keyword(
    keyword_id: UUID, body: KeywordUpdate, session: Session = Depends(get_session)
) -> KeywordRead:
    kw = session.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="关键词不存在")
    if body.text is not None:
        text = body.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="关键词不能为空")
        dup = session.exec(
            select(Keyword).where(Keyword.text == text, Keyword.id != keyword_id)
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"关键词「{text}」已存在")
        kw.text = text
    if body.category is not None:
        kw.category = body.category
    kw.updated_at = datetime.now(UTC)
    session.add(kw)
    session.commit()
    session.refresh(kw)
    return _to_read(session, kw)


@router.patch("/{keyword_id}/toggle", response_model=KeywordRead)
def toggle_keyword(keyword_id: UUID, session: Session = Depends(get_session)) -> KeywordRead:
    kw = session.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="关键词不存在")
    kw.is_active = not kw.is_active
    kw.updated_at = datetime.now(UTC)
    session.add(kw)
    session.commit()
    session.refresh(kw)
    return _to_read(session, kw)


@router.delete("/{keyword_id}", status_code=204)
def delete_keyword(keyword_id: UUID, session: Session = Depends(get_session)) -> None:
    kw = session.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="关键词不存在")
    # 不级联删除热点：热点保留，关联置空（FR-1.4）
    for hs in session.exec(select(Hotspot).where(Hotspot.keyword_id == keyword_id)).all():
        hs.keyword_id = None
        session.add(hs)
    session.delete(kw)
    session.commit()
