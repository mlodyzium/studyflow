from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.schemas.pagination import Page

T = TypeVar("T")


def paginate(db: Session, query: Select, page: int, page_size: int) -> Page[T]:
    total_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = db.scalar(total_query) or 0
    items = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))

    return Page(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )
