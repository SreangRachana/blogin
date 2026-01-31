import uuid
from datetime import datetime
from typing import Optional, List, Generic, TypeVar
from pydantic import BaseModel, Field, model_validator


class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class CommentCreate(CommentBase):
    post_id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None


class CommentUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=5000)


class CommentInDB(CommentBase):
    id: uuid.UUID
    post_id: uuid.UUID
    author_id: uuid.UUID
    parent_id: Optional[uuid.UUID]
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    edited_at: Optional[datetime] = None
    edited: bool = False
    edited_at_formatted: Optional[str] = None

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def compute_edited_flag(self):
        self.edited = self.edited_at is not None
        if self.edited_at:
            self.edited_at_formatted = (
                f"edited - {self.edited_at.strftime('%b %d, %Y %I:%M %p')}"
            )
        return self


class CommentResponse(CommentInDB):
    pass


class CommentWithReplies(CommentInDB):
    replies: List["CommentWithReplies"] = []


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Success"
    data: Optional[T] = None
    error: Optional[str] = None


class PaginatedResponse(APIResponse, Generic[T]):
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
