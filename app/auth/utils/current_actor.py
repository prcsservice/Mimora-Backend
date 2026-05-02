"""Resolve the caller as either a Customer (User) or an Artist from a Bearer token.

Used by booking endpoints that may be called by either party (e.g. cancel, detail).
"""
from typing import Literal, Tuple, Union

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth.database import get_db
from app.auth.firebase import verify_token
from app.auth.models import Artist, User

ActorKind = Literal["customer", "artist"]
Actor = Union[User, Artist]


async def get_current_actor(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> Tuple[Actor, ActorKind]:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ")[1]
    try:
        decoded = verify_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {e}")

    firebase_uid = decoded.get("uid")
    email = decoded.get("email")
    phone = decoded.get("phone_number")
    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Invalid token: no uid")

    # Try Artist first (more constrained table); fallback to Customer.
    artist = db.query(Artist).filter(Artist.firebase_uid == firebase_uid).first()
    if not artist and email:
        artist = db.query(Artist).filter(Artist.email == email).first()
    if not artist and phone:
        artist = db.query(Artist).filter(Artist.phone_number == phone).first()
    if artist:
        return artist, "artist"

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
    if not user and phone:
        user = db.query(User).filter(User.phone_number == phone).first()
    if user:
        return user, "customer"

    raise HTTPException(status_code=404, detail="No matching customer or artist account")
