from __future__ import annotations
from datetime import timezone, datetime
from typing import Annotated
from pydantic import ConfigDict, EmailStr, Field, computed_field
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel, Relationship, Field as SQLModelField


class UserBase(SQLModel):
    username: Annotated[str, SQLModelField(min_length=1, max_length=50, unique=True, nullable=False)]
    email: Annotated[EmailStr, SQLModelField(max_length=120, unique=True, nullable=False)]
    image_file: Annotated[str | None, SQLModelField(min_length=1, max_length=200, nullable=True, default=None)]
    
    @computed_field
    @property
    def image_path(self) -> str:
        if self.image_file:
            return f"/media/profile_pics/{self.image_file}"
        return "/media/profile_pics/default.jpg"

class User(UserBase, table=True):
    __tablename__ = "users"
    id: Annotated[int | None, SQLModelField(default=None, primary_key=True, index=True)]
    posts: Mapped[list["Post"]] = Relationship(
        sa_relationship=relationship("Post", back_populates="author", cascade="all, delete-orphan"))


class UserCreate(UserBase):
    pass


class UserUpdate(UserBase):
    username: Annotated[str | None, SQLModelField(default=None, min_length=1, max_length=50, unique=True, nullable=False)]
    email: Annotated[EmailStr | None, SQLModelField(default=None, max_length=120, unique=True, nullable=False)]
    image_file: Annotated[str | None, SQLModelField(default=None, min_length=1, max_length=200, nullable=True)]


class UserResponse(UserBase):
    id: Annotated[int | None, SQLModelField(default=None, primary_key=True, index=True)]



class PostBase(SQLModel):
    title: Annotated[str, SQLModelField(min_length=1, max_length=100, index=True)]
    content: Annotated[str, SQLModelField(min_length=1)]


class Post(PostBase, table=True):
    __tablename__ = "posts"
    id: Annotated[int | None, SQLModelField(default=None, primary_key=True)]
    date_posted: Annotated[datetime, SQLModelField(
        sa_column=Column(DateTime(timezone=True)),
        default_factory=lambda: datetime.now(tz=timezone.utc))]
    user_id: Annotated[int, SQLModelField(foreign_key="users.id", nullable=False, index=True)]
    author: Mapped[User | None] = Relationship(
        sa_relationship=relationship("User", back_populates="posts"))

class PostCreate(PostBase):
    user_id: int


class PostUpdate(PostBase):
    title: Annotated[str | None, SQLModelField(default=None, min_length=1, max_length=100)]
    content: Annotated[str | None, SQLModelField(default=None, min_length=1)]


class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    date_posted: datetime
    author: UserResponse


DATABASE_URL = "sqlite+aiosqlite:///./blog.db"

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)


async_sessioin = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with async_sessioin() as session:
        yield session

