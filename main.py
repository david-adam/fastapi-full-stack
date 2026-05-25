from typing import Annotated
from fastapi import FastAPI, Request, status, HTTPException, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from . import models
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from contextlib import asynccontextmanager
from .routers import posts, users

@asynccontextmanager
async def create_db_resource(_app: FastAPI):
    # start up
    async with models.engine.begin() as conn:
        await conn.run_sync(models.SQLModel.metadata.create_all)
    yield
    # shutdown
    await models.engine.dispose()

app = FastAPI(lifespan=create_db_resource )
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")
templates = Jinja2Templates(directory="templates")

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])

@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
async def home(request: Request, db: Annotated[AsyncSession, Depends(models.get_db)]):
    
    results = await db.execute(select(models.Post).options(selectinload(models.Post.author)).order_by(models.Post.date_posted.desc()))
    posts = results.scalars().all()

    return templates.TemplateResponse(request, 
        "home.html",
        {"posts": posts, "title": "Home Page"}
    )


@app.get("/posts/{post_id}", include_in_schema=False)
async def post_page(request: Request, post_id: int, db: Annotated[AsyncSession, Depends(models.get_db)]):
    
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(col(models.Post.id) == post_id))
    post = result.scalars().first()

    if post:
        title = post.title[:50]
        return templates.TemplateResponse(request,
            "post.html", 
            {"post": post, "title": title}
        )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")


@app.get("/users/{user_id}/posts", include_in_schema=False, name="user_posts")
async def user_posts_page(
    request: Request,
    user_id: int,
    db: Annotated[AsyncSession, Depends(models.get_db)],
):
    result = await db.execute(select(models.User).where(col(models.User.id) == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    results = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(col(models.Post.user_id) == user_id))
    posts = results.scalars().all()
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {"posts": posts, "user": user, "title": f"{user.username}'s Posts"},
    )

@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(request: Request, exc: StarletteHTTPException):

    if request.url.path.startswith("/api"):
        return await http_exception_handler(request, exc)
    
    message = (
        exc.detail if exc.detail 
        else "An error occurred. Please check your request and try again."
    )

    return templates.TemplateResponse(
        request,
        "error.html", 
        {
            "status_code": exc.status_code,
            "title": exc.status_code,
            "message": message
        },
        status_code=exc.status_code
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exc)

    return templates.TemplateResponse(request,"error.html", 
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request. Please check your input and try again."
        
         },
         status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )