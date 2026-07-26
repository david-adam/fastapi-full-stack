# Users, authentication, and profile images

This domain covers registration, login, current-user lookup, account changes, password reset, and S3-backed profile pictures. The core evidence is in `models.py`, `auth.py`, `routers/users.py`, `image_utils.py`, `email_utils.py`, and the account/auth templates.

## Data model and schemas

`models.py` defines the user-related types:

- `UserBase` — shared `username`, optional `image_file`, and computed `image_path`.
- `User` — database table `users` with `id`, unique `email`, `password_hash`, `posts`, and `reset_tokens` relationships.
- `UserCreate` — registration payload, including `password` with minimum length 8.
- `UserUpdate` — optional `username` and `email` for profile edits.
- `UserPublic` — public response with `id`, `username`, `image_file`, and computed `image_path`.
- `UserPrivate` — extends `UserPublic` with `email`.
- `Token` — bearer token response.
- `PasswordResetToken` — table with `user_id`, SHA-256 token hash, expiry, and created timestamp.
- `ForgotPasswordRequest`, `ResetPasswordRequest`, and `ChangePasswordRequest` — password-flow payloads.

Relationships on `User.posts` and `User.reset_tokens` use `cascade="all, delete-orphan"`, so deleting a user also removes owned posts and reset-token rows through the ORM relationship.

## Registration

`POST /api/users` in `routers/users.py`:

1. Checks for an existing username case-insensitively with `func.lower(...)`.
2. Checks for an existing email case-insensitively.
3. Stores the email lowercased.
4. Hashes the password with `auth.hash_password()` using `pwdlib.PasswordHash.recommended()`.
5. Returns `UserPrivate` without exposing the password or `password_hash`.

`templates/register.html` performs client-side password confirmation and posts JSON to `/api/users`, then redirects to `/login` after success.

## Login and current user

`POST /api/users/token` accepts `OAuth2PasswordRequestForm`. The form field is still named `username`, but the app treats it as the user's email address.

Login behavior:

1. Look up the user by lowercased email.
2. Verify the password with `auth.verify_password()`.
3. Create a JWT with `sub` set to `str(user.id)` and expiry from `settings.access_token_expire_minutes`.
4. Return `Token(access_token=..., token_type="bearer")`.

`auth.py` defines:

- `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/users/token")`
- `create_access_token()`
- `verify_access_token()`, which requires `exp` and `sub`
- `get_current_user()`, which validates the token, parses the `sub` as an integer user id, loads the user from the database, and returns HTTP 401 on invalid/missing users
- `CurrentUser`, the reusable annotated dependency

`static/js/auth.js` stores `access_token` in `localStorage`, caches `/api/users/me`, clears invalid tokens, and provides `logout()`, `getToken()`, `setToken()`, and `clearUserCache()` helpers.

## Profile and account management

`PATCH /api/users/{user_id}` updates the current user's username/email only when `user_id == current_user.id`. It repeats case-insensitive duplicate checks and stores new emails lowercased.

`DELETE /api/users/{user_id}` also requires the current user to match the path user id. It deletes the database user, commits, and then deletes the old S3 profile image if one existed.

`templates/account.html` is the browser control center for:

- Displaying `/api/users/me` data.
- Updating username/email.
- Uploading a profile picture.
- Changing password.
- Logging out.
- Deleting the account.

The UI redirects unauthenticated users to `/login`, but server-side authorization still happens in the router.

## Password reset and password change

### Forgot password

`POST /api/users/forgot-password`:

1. Looks up the submitted email case-insensitively.
2. If a user exists, deletes all previous reset tokens for that user.
3. Generates a random URL-safe token in `auth.generate_reset_token()`.
4. Stores only `hash_reset_token(token)` in `password_reset_tokens`.
5. Sets `expires_at` from `settings.reset_token_expire_minutes`.
6. Schedules `email_utils.send_password_reset_email()` as a FastAPI background task.
7. Always returns the same generic 202 message so callers cannot enumerate accounts.

`templates/forgot_password.html` posts to this endpoint and shows a generic success message.

### Reset password

`POST /api/users/reset-password`:

1. Hashes the submitted token.
2. Looks up a matching `PasswordResetToken`.
3. Rejects missing or expired tokens with HTTP 400.
4. Loads the token's user.
5. Stores the new password hash.
6. Deletes all reset tokens for that user.
7. Commits and returns a success message.

`templates/reset_password.html` reads the token query parameter client-side, posts JSON to `/api/users/reset-password`, and redirects to `/login` on success. `main.py` gives this page `Referrer-Policy: no-referrer`.

### Change password

`PATCH /api/users/me/password` verifies the current password, stores the new hash, deletes outstanding reset tokens for the user, and returns a success message.

## Profile picture flow

`PATCH /api/users/{user_id}/picture` requires the authenticated user to match the path id.

Flow:

1. Read the uploaded file bytes.
2. Reject files larger than `settings.max_upload_size_bytes`.
3. Process the image in a threadpool via `image_utils.process_profile_image()`.
4. Use Pillow to apply EXIF orientation, crop/resize to 300x300, convert to RGB if needed, and save as a JPEG with a UUID filename.
5. Upload to S3 under `profile_pics/{filename}` via `image_utils.upload_profile_image()`.
6. Update `current_user.image_file` and commit.
7. Delete the old S3 object after the new database state is committed.

`DELETE /api/users/{user_id}/picture` clears `image_file`, commits, then deletes the old S3 object. If no custom picture exists, it returns HTTP 400.

`models.UserBase.image_path` returns an S3 URL when `image_file` is set and `/static/profile_pics/default.jpg` otherwise.

## Integration watch points

- `email_utils.send_password_reset_email()` renders the email expiry using `settings.access_token_expire_minutes`, while reset-token rows use `settings.reset_token_expire_minutes`; align those if product copy must match actual expiry.
- S3 upload is committed to object storage before the DB update. If the database commit fails after upload, an orphan S3 object could remain.
- Old S3 image deletion happens after DB commit. If deletion fails, the app state is correct but the old object may remain.
- `image_path` assumes AWS public URL shape even when `S3_ENDPOINT_URL` is configured.
- Password reset emails include the raw token in a URL built from `settings.frontend_url`; keep that URL HTTPS in production.

## Tests that protect this area

`tests/test_users.py` currently covers:

- Registration validation errors.
- Duplicate email rejection.
- Successful user creation without exposing password fields.
- Profile picture upload to moto-backed S3.
- Forgot-password background email scheduling.

Add tests when changing profile update/delete, password reset completion, password change, expired token behavior, account deletion cascades, and S3 failure handling.
