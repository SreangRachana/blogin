from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from jose import jwt, JWTError
import uuid

from app.database import get_db
from app.schemas import PostCreate, PostUpdate, PostResponse, APIResponse
from app.models import Post
from app.services.post_service import (
    get_post_by_id,
    get_post_by_slug,
    create_post,
    update_post,
    delete_post,
    list_posts,
    increment_view_count,
    get_all_tags,
    get_posts_by_author,
)
from app.config import get_settings

router = APIRouter(tags=["Posts"])
security = HTTPBearer()
settings = get_settings()


def get_current_user_id(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )
        return uuid.UUID(user_id)
    except JWTError:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )


@router.get("/", response_model=APIResponse)
async def list_all_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(draft|published|archived)$"),
    author_id: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    skip = (page - 1) * limit
    author_uuid = uuid.UUID(author_id) if author_id else None

    results, total = list_posts(
        db,
        status=status,
        author_id=author_uuid,
        tag=tag,
        search=search,
        skip=skip,
        limit=limit,
    )
    total_pages = (total + limit - 1) // limit

    return APIResponse(
        success=True,
        data={
            "items": [
                {
                    "id": str(post.id),
                    "author_id": str(post.author_id),
                    "author_username": username,
                    "title": post.title,
                    "slug": post.slug,
                    "summary": post.summary,
                    "status": post.status,
                    "view_count": post.view_count,
                    "tags": [
                        {"id": str(t.id), "name": t.name, "slug": t.slug}
                        for t in post.tags
                    ],
                    "created_at": post.created_at.isoformat(),
                    "published_at": post.published_at.isoformat()
                    if post.published_at
                    else None,
                }
                for post, username in results
            ],
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        },
        message="Posts retrieved successfully",
        errors=None,
    )


@router.get("/{slug}/", response_model=APIResponse)
async def get_post(slug: str, db: Session = Depends(get_db)):
    post = get_post_by_slug(db, slug)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Increment view count
    increment_view_count(db, post.id)

    # Get author username
    from sqlalchemy import text

    result = db.execute(
        text("SELECT username FROM users.profiles WHERE user_id = :user_id"),
        {"user_id": str(post.author_id)},
    ).fetchone()
    author_username = result[0] if result else None

    return APIResponse(
        success=True,
        data={
            "id": str(post.id),
            "author_id": str(post.author_id),
            "author_username": author_username,
            "title": post.title,
            "slug": post.slug,
            "content": post.content,
            "summary": post.summary,
            "status": post.status,
            "view_count": post.view_count + 1,  # Already incremented
            "tags": [
                {"id": str(t.id), "name": t.name, "slug": t.slug} for t in post.tags
            ],
            "created_at": post.created_at.isoformat(),
            "updated_at": post.updated_at.isoformat(),
            "published_at": post.published_at.isoformat()
            if post.published_at
            else None,
        },
        message="Post retrieved successfully",
        errors=None,
    )


@router.post("/", response_model=APIResponse)
async def create_new_post(
    post_data: PostCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    user_id = get_current_user_id(token)

    post = create_post(db, user_id, post_data)

    return APIResponse(
        success=True,
        data={
            "id": str(post.id),
            "slug": post.slug,
            "title": post.title,
            "status": post.status,
            "created_at": post.created_at.isoformat(),
        },
        message="Post created successfully",
        errors=None,
    )


@router.put("/{post_identifier}/", response_model=APIResponse)
async def update_existing_post(
    post_identifier: str,
    post_data: PostUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    user_id = get_current_user_id(token)

    # Try to get post by UUID first, then by slug
    post = None
    try:
        post = get_post_by_id(db, uuid.UUID(post_identifier))
    except ValueError:
        # Not a valid UUID, try slug instead
        pass

    if not post:
        post = get_post_by_slug(db, post_identifier)

    if not post:
        raise HTTPException(
            status_code=404, detail="Post not found or you don't have permission"
        )

    # Check if user is the author
    if post.author_id != user_id:
        raise HTTPException(
            status_code=403, detail="You don't have permission to update this post"
        )

    # Update the post
    from app.services.post_service import update_post as service_update_post

    updated_post = service_update_post(db, post.id, user_id, post_data)
    if not updated_post:
        raise HTTPException(
            status_code=404, detail="Post not found or you don't have permission"
        )

    return APIResponse(
        success=True,
        data={
            "id": str(updated_post.id),
            "slug": updated_post.slug,
            "title": updated_post.title,
            "status": updated_post.status,
            "updated_at": updated_post.updated_at.isoformat(),
        },
        message="Post updated successfully",
        errors=None,
    )


@router.delete("/{post_identifier}/", response_model=APIResponse)
async def delete_existing_post(
    post_identifier: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    user_id = get_current_user_id(token)

    # Try to get post by UUID first, then by slug
    post = None
    try:
        post = get_post_by_id(db, uuid.UUID(post_identifier))
    except ValueError:
        # Not a valid UUID, try slug instead
        pass

    if not post:
        post = get_post_by_slug(db, post_identifier)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check if user is the author
    if post.author_id != user_id:
        raise HTTPException(
            status_code=403, detail="You don't have permission to delete this post"
        )

    # Delete the post
    db.delete(post)
    db.commit()

    return APIResponse(
        success=True, data=None, message="Post deleted successfully", errors=None
    )


@router.get("/tags", response_model=APIResponse)
async def list_tags(db: Session = Depends(get_db)):
    tags = get_all_tags(db)

    return APIResponse(
        success=True,
        data={
            "items": [{"id": str(t.id), "name": t.name, "slug": t.slug} for t in tags],
        },
        message="Tags retrieved successfully",
        errors=None,
    )


@router.get("/authors/{author_id}/posts", response_model=APIResponse)
async def get_posts_by_author_id(
    author_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    skip = (page - 1) * limit
    results, total = get_posts_by_author(
        db, uuid.UUID(author_id), skip=skip, limit=limit
    )
    total_pages = (total + limit - 1) // limit

    return APIResponse(
        success=True,
        data={
            "items": [
                {
                    "id": str(post.id),
                    "author_id": str(post.author_id),
                    "author_username": username,
                    "title": post.title,
                    "slug": post.slug,
                    "summary": post.summary,
                    "status": post.status,
                    "view_count": post.view_count,
                    "tags": [
                        {"id": str(t.id), "name": t.name, "slug": t.slug}
                        for t in post.tags
                    ],
                    "created_at": post.created_at.isoformat(),
                    "published_at": post.published_at.isoformat()
                    if post.published_at
                    else None,
                }
                for post, username in results
            ],
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        },
        message="Author posts retrieved successfully",
        errors=None,
    )
