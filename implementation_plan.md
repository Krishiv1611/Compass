# Google & GitHub OAuth Integration Plan

We need to implement the full OAuth 2.0 flow for Google and GitHub. This includes exposing authorization URLs from the backend, adding redirect triggers in the frontend, capturing the authorization code via a callback page, and exchanging it for a JWT session.

## Proposed Changes

### Backend

#### [MODIFY] [auth.py](file:///d:/projects/compass/backend/routers/auth.py)
- Add `GET /auth/oauth/google/url` and `GET /auth/oauth/github/url` endpoints to return the consent screen URLs. This keeps Client IDs on the backend and avoids duplication.

---

### Frontend

#### [NEW] [AuthCallback.tsx](file:///d:/projects/compass/frontend/src/pages/AuthCallback.tsx)
- Create a new callback page that:
  1. Identifies the provider (Google/GitHub) from the route or search parameters.
  2. Extracts the `code` query parameter.
  3. Sends a POST request to `/auth/oauth/google` or `/auth/oauth/github` with the code.
  4. Saves the resulting JWT access token.
  5. Redirects the user back to the chat dashboard.

#### [MODIFY] [App.tsx](file:///d:/projects/compass/frontend/src/App.tsx)
- Register the `/auth/callback` route.

#### [MODIFY] [LoginModal.tsx](file:///d:/projects/compass/frontend/src/components/auth/LoginModal.tsx)
- Call the URL endpoints and redirect the window to Google/GitHub consent screens when the OAuth buttons are clicked.

#### [MODIFY] [api.ts](file:///d:/projects/compass/frontend/src/api.ts)
- Add endpoints to fetch the OAuth URLs and exchange the authorization codes.

## Step-by-Step Configuration Guide (for your `.env`)

To make these flows work, you must add the credentials to `backend/.env`.

### 1. Google OAuth Setup
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one).
3. Navigate to **APIs & Services > Credentials**.
4. Click **Create Credentials > OAuth client ID**.
5. Select application type: **Web application**.
6. Add **Authorized JavaScript origins**: `http://localhost:5173` (Must NOT contain a path or end with `/`).
7. Add **Authorized redirect URIs**: `http://localhost:5173/auth/callback` (This is where the path goes).
8. In `backend/.env`, add:
   ```env
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   ```

### 2. GitHub OAuth Setup
1. Go to your GitHub account settings: **Developer Settings > OAuth Apps**.
2. Click **New OAuth App**.
3. Set Homepage URL to: `http://localhost:5173`.
4. Set Authorization callback URL to: `http://localhost:5173/auth/callback`.
5. Click **Register application**.
6. Copy the **Client ID** and generate a new **Client Secret**.
7. In `backend/.env`, add:
   ```env
   GITHUB_CLIENT_ID=your_github_client_id
   GITHUB_CLIENT_SECRET=your_github_client_secret
   ```

## Verification Plan

### Manual Verification
1. Run backend (`uvicorn`) and frontend (`npm run dev`).
2. Open the Login Modal, click "Continue with Google".
3. Verify it redirects to the Google login page.
4. Complete login, and verify you are redirected back to `http://localhost:5173/auth/callback` and then into `/chat` with a valid logged-in session.
5. Repeat for GitHub.
