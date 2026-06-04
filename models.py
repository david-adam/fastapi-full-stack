from __future__ import annotations
from datetime import timezone, datetime
from typing import Annotated
from pydantic import ConfigDict, EmailStr, computed_field
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Relationship, Field as SQLModelField
from config import settings

class UserBase(SQLModel):
    username: Annotated[str, SQLModelField(min_length=1, max_length=50, unique=True, nullable=False)]
    image_file: Annotated[str | None, SQLModelField(max_length=200, nullable=True, default=None)] = None
    
    @computed_field
    @property
    def image_path(self) -> str:
        if self.image_file:
            return f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com/profile_pics/{self.image_file}"
        return "/static/profile_pics/default.jpg"

class User(UserBase, table=True):
    __tablename__ = "users" # type: ignore
    id: Annotated[int | None, SQLModelField(default=None, primary_key=True, index=True)] = None
    email: Annotated[EmailStr, SQLModelField(max_length=120, unique=True, nullable=False)]
    password_hash: Annotated[str, SQLModelField(max_length=200, nullable=False)]
    posts: Mapped[list["Post"]] = Relationship(
        sa_relationship=relationship("Post", back_populates="author", cascade="all, delete-orphan"))
    reset_tokens: Mapped[list[PasswordResetToken]] = Relationship(
        sa_relationship=relationship("PasswordResetToken",back_populates="user", cascade="all, delete-orphan")
    )


class UserCreate(UserBase):
    email: Annotated[EmailStr, SQLModelField(max_length=120, unique=True, nullable=False)]
    password: Annotated[str, SQLModelField(min_length=8)]


class UserUpdate(UserBase):
    username: Annotated[str | None, SQLModelField(default=None, min_length=1, max_length=50, unique=True, nullable=False)] # type: ignore
    email: Annotated[EmailStr | None, SQLModelField(default=None, max_length=120, unique=True, nullable=False)]


class Token(SQLModel):
    access_token: str
    token_type: str


class UserPublic(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class UserPrivate(UserPublic):
    email: EmailStr


class PostBase(SQLModel):
    title: Annotated[str, SQLModelField(min_length=1, max_length=100, index=True)]
    content: Annotated[str, SQLModelField(min_length=1)]


class Post(PostBase, table=True):
    __tablename__ = "posts" # type: ignore
    id: Annotated[int | None, SQLModelField(default=None, primary_key=True)] = None
    date_posted: Annotated[datetime, SQLModelField(
        sa_column=Column(DateTime(timezone=True)),
        default_factory=lambda: datetime.now(tz=timezone.utc))]
    user_id: Annotated[int, SQLModelField(foreign_key="users.id", nullable=False, index=True)]
    likes: Annotated[int, SQLModelField(default=0, sa_column_kwargs={"server_default": "0"})] = 0
    author: Mapped[User] = Relationship(
        sa_relationship=relationship("User", back_populates="posts"))

class PostCreate(PostBase):
    pass


class PostUpdate(PostBase):
    title: Annotated[str | None, SQLModelField(default=None, min_length=1, max_length=100)] # type: ignore
    content: Annotated[str | None, SQLModelField(default=None, min_length=1)] # type: ignore


class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    date_posted: datetime
    author: UserPublic


class PaginatedPostsResponse(SQLModel):
    posts: list[PostResponse]
    total: int
    skip: int
    limit: int
    has_more: bool


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_tokens" # type: ignore

    id: Annotated[int | None, SQLModelField(int, primary_key=True, index=True)] = None
    user_id: Annotated[int, SQLModelField(foreign_key="users.id", nullable=False)]
    token_hash: Annotated[str, SQLModelField(max_length=64, unique=True, nullable=False)]
    expires_at: Annotated[datetime, SQLModelField(
        DateTime(timezone=True),
        nullable=False,
    )]
    created_at: Annotated[datetime, SQLModelField(
        sa_column=Column(DateTime(timezone=True)),
        default_factory=lambda: datetime.now(timezone.utc),
    )]

    user: Mapped[User] =  Relationship(
        sa_relationship=relationship("User", back_populates="reset_tokens"))


class ForgotPasswordRequest(SQLModel):
    email: EmailStr = SQLModelField(max_length=120)


class ResetPasswordRequest(SQLModel):
    token: str
    new_password: str = SQLModelField(min_length=8)


class ChangePasswordRequest(SQLModel):
    current_password: str
    new_password: str = SQLModelField(min_length=8)
