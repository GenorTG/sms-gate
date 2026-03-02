# Zapier integration

Copy-pastable blocks for sending SMS from Zapier.

## 1. Webhook to Web UI (recommended)

One request = one SMS. No JWT handling in Zapier.

- **App**: Webhooks by Zapier (or any "POST" action).
- **URL**: Your Web UI URL + `/api/send`. Examples:
  - Local: `http://your-server:4842/api/send`
  - Production: `https://sms.yourcompany.com/api/send` (reverse proxy to port 4842)
- **Method**: POST
- **Headers**: `Content-Type: application/json`
- **Body (JSON)**:

```json
{
  "phone": "+48123456789",
  "message": "Hello from Zapier"
}
```

- Phone must be E.164 (e.g. `+48123456789`).
- Response: 202 and `{"success": true, ...}` on success; 4xx/5xx and `{"success": false, "error": "..."}` on failure.

## 2. Direct sms-gate API (two steps)

Use this if Zapier talks to the sms-gate server directly (e.g. internal URL) and you prefer not to use the Web UI.

**Step 1 – Get token**

- **URL**: `https://your-sms-gate-url/api/3rdparty/v1/auth/token`
- **Method**: POST
- **Auth**: Basic (username = device username from Android app, password = device password from Android app)
- **Headers**: `Content-Type: application/json`
- **Body**:

```json
{
  "scopes": ["messages:send"],
  "ttl": 86400
}
```

- Capture the `access_token` from the response (e.g. in a Zapier field).

**Step 2 – Send message**

- **URL**: `https://your-sms-gate-url/api/3rdparty/v1/messages`
- **Method**: POST
- **Headers**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <access_token>` (use the token from Step 1)
- **Body**:

```json
{
  "phoneNumbers": ["+48123456789"],
  "textMessage": {
    "text": "Hello from Zapier"
  }
}
```

- Success: HTTP 202 and a `Location` header to check message status.

---

For company deployment, expose the Web UI behind a reverse proxy (e.g. `https://sms.company.com` → port 4842) and use that URL in Zapier.
