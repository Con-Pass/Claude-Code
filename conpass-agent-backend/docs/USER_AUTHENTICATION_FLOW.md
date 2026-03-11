# Authentication Flow for ConPass Agent

## Overview

The ConPass agent backend now relies on the ConPass platform to issue and manage user
authentication. The frontend retrieves the platform’s session cookie
(`auth-token`) and forwards it on every request. The agent backend verifies this
token with ConPass before processing API calls and passes it along to downstream
services.

There is no longer any JWT minting or user-info based identity handling inside the
agent backend.

---

## 1. Requirements

- Every client request **must** include the `auth-token` cookie obtained from the
  ConPass platform.
- No additional `UserInfo` payload is required; chat payloads now contain only the
  chat history and session type.
- If the cookie is missing or invalid, the backend responds with `401
  Unauthorized`.

Example request headers:

```
Cookie: auth-token=<conpass-session-token>
Content-Type: application/json
```

---

## 2. Middleware Verification

The `JWTAuthMiddleware` validates tokens for all protected endpoints.

1. Extracts `auth-token` from the incoming cookie.
2. Calls `GET {CONPASS_API_BASE_URL}/user` with the same cookie to verify the
   session with ConPass.
3. On success, stores the token on `request.state.conpass_token` for downstream
   handlers.
4. On failure, returns an error response:
   - `401` for invalid/expired ConPass tokens.
   - `503` if the ConPass service is unreachable.
   - `500` for unexpected middleware errors.

---

## 3. Chat Payload Shape

Only chat messages (and optional session metadata) are required.

```json
{
  "messages": [
    { "role": "user", "content": "Fetch active contracts" }
  ],
  "data": {
    "type": "general"
  }
}
```

The backend no longer expects a `user` field inside `data`.

---

## 4. Downstream ConPass API Usage

- `ConpassApiService` receives the verified token and forwards it as
  `Cookie: auth-token=<token>` when calling the ConPass backend (e.g.
  `/contract/paginate`, `/contract/body/list`).
- The token is not altered or re-issued by the agent backend.

---

## 5. Legacy Components

- `ConpassCookieService` and the `agent-auth-token` flow remain in the repo for
  reference but are no longer used by the chat endpoints.
- Streaming response helpers (`VercelStreamResponse`) no longer set cookies; the
  frontend already maintains the session.

---

## 6. Error Cases

- **Missing `auth-token` cookie** → `401 Authentication token missing`
- **Invalid/expired token (ConPass returns 401/403)** → `401 Invalid ConPass authentication token`
- **ConPass user endpoint unreachable** → `503 Unable to reach ConPass authentication service`
- **Unexpected middleware error** → `500 Internal authentication error`

---

## 7. Environment Variables

The authentication middleware uses the existing application settings:

```env
CONPASS_API_BASE_URL=https://www.xyz.con-pass.jp/api
```

No additional secrets are required for token verification.

---

## Summary Table

| API Endpoint         | Requires `auth-token` Cookie? | Additional User Payload Needed? | Issues/Mints Tokens? |
| -------------------- | :----------------------------: | :-----------------------------: | :------------------: |
| `/api/v1/chat`       |              YES               |               NO                |         NO           |
| `/api/v1/chat/request` |            YES               |               NO                |         NO           |

All other public documentation (Swagger/health endpoints) remain unauthenticated
and bypass the middleware.
