"""Demo-identity-bound friend request endpoints."""
import sqlite3

from fastapi import APIRouter, HTTPException

from backend.dependencies import CurrentUser
from backend.friendships import (
    create_friend_request, list_friend_requests, respond_to_friend_request,
)
from backend.models import FriendRequest, FriendRequestCreate, FriendRequestRespond
from backend.repositories import get_user

router = APIRouter(prefix="/friend-requests", tags=["friend requests"])


@router.post("", response_model=FriendRequest, status_code=201)
def send_request(body: FriendRequestCreate, current_user: CurrentUser) -> FriendRequest:
    if body.recipient_id == current_user.id:
        raise HTTPException(status_code=422, detail="Cannot send yourself a friend request")
    if get_user(body.recipient_id) is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    try:
        return create_friend_request(current_user.id, body.recipient_id)
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorname == "SQLITE_CONSTRAINT_UNIQUE":
            raise HTTPException(
                status_code=409,
                detail="A pending request or friendship already exists",
            ) from error
        raise


@router.get("", response_model=list[FriendRequest])
def get_my_requests(current_user: CurrentUser) -> list[FriendRequest]:
    return list_friend_requests(current_user.id)


@router.post("/{request_id}/respond", response_model=FriendRequest)
def respond(
    request_id: str, body: FriendRequestRespond, current_user: CurrentUser,
) -> FriendRequest:
    try:
        return respond_to_friend_request(request_id, current_user.id, body.decision)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
