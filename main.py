from email.policy import HTTP
from typing import Annotated
from fastapi import FastAPI, Request, status, HTTPException, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_103_EARLY_HINTS
from . import models
from sqlmodel import col, select, Session
from contextlib import asynccontextmanager


@asynccontextmanager
async def create_db_resource(app: FastAPI):
    models.create_db_and_tables()
    yield

app = FastAPI(lifespan=create_db_resource )
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")
templates = Jinja2Templates(directory="templates")




@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
def home(request: Request, db: Annotated[Session, Depends(models.get_db)]):
    
    posts = db.exec(select(models.Post)).all()


    return templates.TemplateResponse(request, 
        "home.html",
        {"posts": posts, "title": "Home Page"}
    )


@app.get("/posts/{post_id}", include_in_schema=False)
def post_page(request: Request, post_id: int, db: Annotated[Session, Depends(models.get_db)]):
    
    post = db.exec(select(models.Post).where(col(models.Post.id) == post_id)).first()

    if post:
        title = post.title[:50]
        return templates.TemplateResponse(request,
            "post.html", 
            {"post": post, "title": title}
        )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")


@app.get("/users/{user_id}/posts", include_in_schema=False, name="user_posts")
def user_posts_page(
    request: Request,
    user_id: int,
    db: Annotated[Session, Depends(models.get_db)],
):
    result = db.exec(select(models.User).where(col(models.User.id) == user_id))
    user = result.first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    result = db.exec(select(models.Post).where(col(models.Post.user_id) == user_id))
    posts = result.all()
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {"posts": posts, "user": user, "title": f"{user.username}'s Posts"},
    )


@app.post(
    "/api/users",
    response_model=models.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(user: models.UserCreate, db: Annotated[Session, Depends(models.get_db)]):
    result = db.exec(
        select(models.User).where(col(models.User.username) == user.username),
    )
    existing_user = result.first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    result = db.exec(
        select(models.User).where(col(models.User.email) == user.email),
    )
    existing_email = result.first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    new_user = models.User(
        username=user.username,
        email=user.email,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get("/api/users/{user_id}", response_model=models.UserResponse)
def get_user(user_id: int, db: Annotated[Session, Depends(models.get_db)]):
    result = db.exec(
        select(models.User).where(col(models.User.id) == user_id),
    )
    user = result.first()
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@app.patch("/api/users/{user_id}", response_model=models.UserResponse)
def update_user(user_id: int, user_update: models.UserUpdate, db: Annotated[Session, Depends(models.get_db)]):
    result = db.exec(
        select(models.User).where(col(models.User.id) == user_id),
    )
    user = result.first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_update.username is not None and user_update.username != user.username:
        existing_user = db.exec(select(models.User).where(col(models.User.username) == user_update.username)).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )

    if user_update.email is not None and user_update.email != user.email:
        existing_email = db.exec(select(models.User).where(col(models.User.email) == user_update.email)).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )

    if user_update.username is not None:
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.image_file is not None:
        user.image_file = user_update.image_file

    db.commit()
    db.refresh(user)
    return user


@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Annotated[Session, Depends(models.get_db)]):
    user = db.exec(select(models.User).where(col(models.User.id) == user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()



@app.get("/api/users/{user_id}/posts", response_model=list[models.PostResponse])
def get_user_posts(user_id: int, db: Annotated[Session, Depends(models.get_db)]):
    result = db.exec(select(models.User).where(col(models.User.id) == user_id))
    user = result.first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    result = db.exec(select(models.Post).where(col(models.Post.user_id) == user_id))
    posts = result.all()
    return posts


@app.post("/api/posts", 
    response_model=models.PostResponse,
    status_code=status.HTTP_201_CREATED
)
def create_post(post: models.PostCreate, db: Annotated[Session, Depends(models.get_db)]):
    result = db.exec(select(models.User).where(col(models.User.id) == post.user_id))
    user = result.first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    new_post = models.Post(
        title=post.title,
        content=post.content,
        user_id=post.user_id,
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post



@app.get("/api/posts", response_model=list[models.PostResponse])
def get_posts(db: Annotated[Session, Depends(models.get_db)]):
    result = db.exec(select(models.Post))
    posts = result.all()
    return posts


@app.get("/api/posts/{post_id}", response_model=models.PostResponse)
def get_post(post_id: int, db: Annotated[Session, Depends(models.get_db)]):
    result = db.exec(select(models.Post).where(col(models.Post.id) == post_id))
    post = result.first()
    if post:
        return post
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")


@app.put("/api/posts/{post_id}", response_model=models.PostResponse)
def update_post_full(post_id: int, post_data: models.PostCreate, db: Annotated[Session, Depends(models.get_db)]):
    result = db.exec(select(models.Post).where(col(models.Post.id) == post_id))
    post = result.first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post_data.user_id != post.user_id:
        user = db.exec(select(models.User).where(col(models.User.id) == post_data.user_id)).first()
        if not user:
            raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    post.title = post_data.title
    post.content = post_data.content
    post.user_id = post_data.user_id

    db.commit()
    db.refresh(post)
    return post 


@app.patch("/api/posts/{post_id}", response_model=models.PostResponse)
def update_post_partial(post_id: int, post_data: models.PostUpdate, db: Annotated[Session, Depends(models.get_db)]):
    result = db.exec(select(models.Post).where(col(models.Post.id) == post_id))
    post = result.first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    update_data = post_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)


    db.commit()
    db.refresh(post)
    return post 


@app.delete("/api/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, db: Annotated[Session, Depends(models.get_db)]):
    result = db.exec(select(models.Post).where(col(models.Post.id) == post_id))
    post = result.first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    db.delete(post)
    db.commit()


@app.exception_handler(StarletteHTTPException)
def general_http_exception_handler(request: Request, exc: StarletteHTTPException):
    message = (
        exc.detail if exc.detail 
        else "An error occurred. Please check your request and try again."
    )
    
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=exc.status_code, content={"detail": message})
    
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
def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "body": exc.body},
        )

    return templates.TemplateResponse(request,"error.html", 
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request. Please check your input and try again."
        
         },
         status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )