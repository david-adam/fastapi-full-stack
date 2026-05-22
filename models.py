from __future__ import annotations
from datetime import UTC, datetime
from typing import Annotated
from pydantic import ConfigDict, EmailStr, Field, computed_field
from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Session, SQLModel, create_engine, Relationship


class UserBase(SQLModel):
    username: Annotated[str, Field(min_length=1, max_length=50, unique=True, nullable=False)]
    email: Annotated[EmailStr, Field(max_length=120, unique=True, nullable=False)]
    image_file: Annotated[str | None, Field(min_length=1, max_length=200, nullable=True, default=None)]
    
    @computed_field
    @property
    def image_path(self) -> str:
        if self.image_file:
            return f"/media/profile_pics/{self.image_file}"
        return "/media/profile_pics/default.jpg"

class User(UserBase, table=True):
    __tablename__ = "users"
    id: Annotated[int | None, Field(default=None, primary_key=True, index=True)]
    posts: Mapped[list["Post"]] = Relationship(
        sa_relationship=relationship("Post", back_populates="author", cascade="all, delete-orphan"))


class UserCreate(UserBase):
    pass


class UserUpdate(UserBase):
    username: Annotated[str | None, Field(default=None, min_length=1, max_length=50, unique=True, nullable=False)]
    email: Annotated[EmailStr | None, Field(default=None, max_length=120, unique=True, nullable=False)]
    image_file: Annotated[str | None, Field(default=None, min_length=1, max_length=200, nullable=True)]


class UserResponse(UserBase):
    id: Annotated[int | None, Field(default=None, primary_key=True, index=True)]



class PostBase(SQLModel):
    title: Annotated[str, Field(min_length=1, max_length=100, index=True)]
    content: Annotated[str, Field(min_length=1)]


class Post(PostBase, table=True):
    __tablename__ = "posts"
    id: Annotated[int | None, Field(default=None, primary_key=True)]
    date_posted: Annotated[datetime, Field(default=datetime.now(tz=UTC))]
    user_id: Annotated[int, Field(foreign_key="users.id", nullable=False, index=True)]
    author: Mapped[User | None] = Relationship(
        sa_relationship=relationship("User", back_populates="posts"))

class PostCreate(PostBase):
    user_id: int


class PostUpdate(PostBase):
    title: Annotated[str | None, Field(default=None, min_length=1, max_length=100)]
    content: Annotated[str | None, Field(default=None, min_length=1)]


class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    date_posted: datetime
    author: UserResponse


DATABASE_URL = "sqlite:///./blog.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

engine.execution_options(autocommit=False, autoflush=False)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_db():
    with Session(engine) as db:
        yield db


if __name__ == "__main__":
    create_db_and_tables()