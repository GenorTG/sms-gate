# Zapier integration

Copy-pastable blocks for sending SMS from Zapier. Credentials are sent with each request; the stack does not store them.

---

## 1. Code by Zapier (custom JavaScript) – recommended

Use **Code by Zapier** with a **JavaScript** step. Set these 4 input variables in Zapier (or map them from previous steps), then paste the code below.

**Input variables** (set in Zapier):

| Variable   | Description |
|-----------|-------------|
| `webuiUrl` | Your Web UI base URL (e.g. `https://sms.yourcompany.com` or `http://your-server:4842`) – no trailing slash |
| `username` | Device username (from Android app: Settings → Cloud Server) |
| `password` | Device password (from Android app) |
| `phone`    | Destination number, E.164 (e.g. `+48123456789`) |
| `message`  | SMS text to send |

**Paste this into the Code step:**

```javascript
const webuiUrl = inputData.webuiUrl;   // e.g. https://sms.yourcompany.com
const username = inputData.username;   // device username from app
const password = inputData.password;   // device password from app
const phone    = inputData.phone;       // e.g. +48123456789
const message  = inputData.message;    // SMS body

const url = webuiUrl.replace(/\/$/, '') + '/api/send';
const res = await fetch(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password, phone, message })
});
const body = await res.json();
return { statusCode: res.status, success: body.success, response: body };
```

In Zapier, add the 5 input fields (`webuiUrl`, `username`, `password`, `phone`, `message`) and map them. The step returns `statusCode`, `success`, and `response` for use in later steps.

---

## 2. Webhook to Web UI (raw POST)

One request = one SMS. Send device credentials in each request (they are not stored on the server).

- **App**: Webhooks by Zapier (or any "POST" action).
- **URL**: Your Web UI URL + `/api/send`. Examples:
  - Local: `http://your-server:4842/api/send`
  - Production: `https://sms.yourcompany.com/api/send` (reverse proxy to port 4842)
- **Method**: POST
- **Headers**: `Content-Type: application/json`
- **Body (JSON)**:

```json
{
  "username": "DEVICE_USERNAME_FROM_APP",
  "password": "DEVICE_PASSWORD_FROM_APP",
  "phone": "+48123456789",
  "message": "Hello from Zapier"
}
```

- `username` and `password` are the device credentials from the Android app (Settings → Cloud Server). They are not stored on the server.
- Phone must be E.164 (e.g. `+48123456789`).
- Response: 202 and `{"success": true, ...}` on success; 4xx/5xx and `{"success": false, "error": "..."}` on failure.

---

## 3. Direct sms-gate API (two steps)

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
