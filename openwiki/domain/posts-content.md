# Posts, content, and pagination

This domain covers blog post storage, APIs, ownership rules, list/detail pages, author pages, pagination, and demo content. Start with `models.py`, `routers/posts.py`, the post-related route handlers in `main.py`, and templates `home.html`, `post.html`, and `user_posts.html`.

## Post model and response shape

`models.py` defines:

- `PostBase` — `title` with length 1-100 and `content` with minimum length 1.
- `Post` — database table `posts` with `id`, timezone-aware `date_posted`, `user_id`, `likes`, and `author` relationship.
- `PostCreate` — required title/content for creates and full updates.
- `PostUpdate` — optional title/content for partial updates.
- `PostResponse` — API response including `id`, `user_id`, `date_posted`, and nested `author: UserPublic`.
- `PaginatedPostsResponse` — response envelope with `posts`, `total`, `skip`, `limit`, and `has_more`.

`Post.likes` exists in the table and model with default 0, but `PostResponse` does not expose it and no router mutates it yet.

## Post API

`routers/posts.py` exposes `/api/posts`:

- `GET /api/posts?skip=0&limit=10` lists posts newest first, eager-loads authors, validates `skip >= 0` and `1 <= limit <= 100`, and returns `PaginatedPostsResponse`.
- `POST /api/posts` requires `CurrentUser`, creates a post for the authenticated user, commits, refreshes the `author`, and returns HTTP 201.
- `GET /api/posts/{post_id}` returns one post with author or HTTP 404.
- `PUT /api/posts/{post_id}` requires ownership and replaces title/content.
- `PATCH /api/posts/{post_id}` requires ownership and updates only provided fields.
- `DELETE /api/posts/{post_id}` requires ownership and returns HTTP 204.

Ownership is enforced by comparing `post.user_id` to `current_user.id`. This is the real security boundary; template controls only improve UX.

## Browser pages

### Home and all-posts page

`main.py` maps both `/` and `/posts` to `home()`.

The handler:

1. Counts all posts.
2. Selects newest posts with `selectinload(models.Post.author)` and `limit(settings.posts_per_page)`.
3. Calculates `has_more = len(posts) < total`.
4. Renders `templates/home.html` with the first page.

`templates/home.html` renders initial posts server-side, then its `Load More Posts` button calls `/api/posts?skip={currentOffset}&limit={limit}` and appends escaped HTML client-side.

### Post detail page

`main.py` maps `/posts/{post_id}` to `post_page()`.

It loads the post and author, uses the first 50 characters of the title as the page title, and renders `templates/post.html`.

`templates/post.html`:

- Displays the post content and author.
- Calls `/api/users/me` through `getCurrentUser()`.
- Shows edit/delete buttons only if the logged-in user owns the post.
- Uses `PATCH /api/posts/{post_id}` for edits.
- Uses `DELETE /api/posts/{post_id}` for deletion.

### Author page

`main.py` maps `/users/{user_id}/posts` to `user_posts_page()`.

It first verifies the user exists, then counts and loads that user's posts. `templates/user_posts.html` mirrors home-page pagination but calls `/api/users/{user_id}/posts` for additional pages.

## User posts API

`GET /api/users/{user_id}/posts` lives in `routers/users.py`, not `routers/posts.py`. It validates that the user exists, counts posts by `user_id`, eager-loads authors, orders newest first, and returns `PaginatedPostsResponse`.

This split matters for agents: user-owned post listing is part of the users router, while general post CRUD is in the posts router.

## Demo content and seed workflow

`populate_db.py` is a destructive seed script for demo/dev environments. It:

1. Deletes existing S3 profile images for users that have `image_file` values.
2. Deletes reset tokens, posts, and users from the database.
3. Uses `httpx.ASGITransport(app=app)` to call the same API endpoints as a client.
4. Creates six demo users.
5. Logs each user in to get bearer tokens.
6. Uploads profile images from `populate_images/` for users that define an image.
7. Creates 44 posts, including the special oldest `POST_44` pagination easter egg.
8. Updates post dates so the demo feed spans roughly 90 days.

Because it clears data and deletes S3 objects, treat `populate_db.py` as a local/demo tool, not a production maintenance script.

## Pagination rules

API pagination uses offset/limit:

- `skip` defaults to 0 and must be non-negative.
- `limit` defaults to 10 for `/api/posts`; user-posts defaults to `settings.posts_per_page`.
- `limit` must be between 1 and 100 on API routes.
- `has_more` is `skip + len(posts) < total` in API responses.

Initial browser pages render `settings.posts_per_page` posts and start client-side `currentOffset` at that same value.

## Change guidance

- If adding new post fields, update `Post`, create/update schemas, `PostResponse`, templates, API tests, and Alembic migrations together.
- If adding likes behavior, remember that the schema and migration groundwork exists but there is no API/UI behavior yet.
- If changing pagination semantics, update both API routers and the client-side `home.html`/`user_posts.html` offset logic.
- If adding comments, tags, or search, decide whether they belong in `routers/posts.py` or a new router before expanding `main.py`.
- Preserve author eager-loading when response models or templates need `post.author`.

## Tests that protect this area

`tests/test_posts.py` covers:

- Empty post list response.
- 404 for missing post detail.
- Authenticated post creation.
- Unauthorized creation rejection.
- Successful owner update.
- Wrong-user update rejection.
- Pagination totals, page sizes, offsets, and `has_more`.

Add coverage for delete behavior, full `PUT` updates, browser-page rendering expectations, user-specific post listing, and any future likes/comment behavior.
