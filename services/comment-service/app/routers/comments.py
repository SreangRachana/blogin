import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import (
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    CommentWithReplies,
    APIResponse,
    PaginatedResponse,
)
from app.services.comment_service import CommentService
from app.routers.dependencies import get_current_user

router = APIRouter(tags=["comments"])


def get_comment_service(db: Session = Depends(get_db)):
    return CommentService(db)


@router.post("", response_model=APIResponse[CommentResponse])
def create_comment(
    comment_in: CommentCreate,
    current_user: dict = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
):
    try:
        comment = service.create(
            obj_in=comment_in, author_id=uuid.UUID(current_user["user_id"])
        )
        return APIResponse(data=comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/post/{post_id}", response_model=PaginatedResponse[list])
def get_comments_by_post(
    post_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: CommentService = Depends(get_comment_service),
):
    result = service.get_by_post(post_id=post_id, page=page, page_size=page_size)

    total_pages = (result["total"] + page_size - 1) // page_size

    return PaginatedResponse(
        data=result["items"],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=total_pages,
    )


@router.post("/post/{post_id}", response_model=APIResponse[CommentResponse])
def create_comment_by_post(
    post_id: uuid.UUID,
    comment_in: CommentCreate,
    current_user: dict = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
):
    """Create a comment on a specific post (post_id from URL)"""
    try:
        # Override post_id from URL
        comment_data = comment_in.model_dump()
        comment_data["post_id"] = post_id
        from app.schemas import CommentCreate as CommentCreateSchema

        comment_with_post = CommentCreateSchema(**comment_data)

        comment = service.create(
            obj_in=comment_with_post, author_id=uuid.UUID(current_user["user_id"])
        )
        return APIResponse(data=comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{comment_id}", response_model=APIResponse[CommentWithReplies])
def get_comment(
    comment_id: uuid.UUID,
    include_replies: bool = Query(True),
    service: CommentService = Depends(get_comment_service),
):
    comment = service.get_by_id(comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    if include_replies:
        comment_tree = service.build_comment_tree(comment)
        return APIResponse(data=comment_tree)

    return APIResponse(data=comment)


@router.put("/{comment_id}", response_model=APIResponse[CommentResponse])
def update_comment(
    comment_id: uuid.UUID,
    comment_in: CommentUpdate,
    current_user: dict = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
):
    comment = service.get_by_id(comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    if str(comment.author_id) != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this comment",
        )

    updated_comment = service.update(comment, comment_in)
    return APIResponse(data=updated_comment)


@router.delete("/{comment_id}", response_model=APIResponse[dict])
def delete_comment(
    comment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
):
    success = service.delete(
        comment_id=comment_id, author_id=uuid.UUID(current_user["user_id"])
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or not authorized",
        )

    return APIResponse(data={"deleted": True})


@router.get("/post/{post_id}/count", response_model=APIResponse[dict])
def get_comment_count(
    post_id: uuid.UUID, service: CommentService = Depends(get_comment_service)
):
    count = service.get_comment_count_by_post(post_id)
    return APIResponse(data={"count": count})
