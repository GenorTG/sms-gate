# Sending SMS via the API (without touching the phone)

After the Android app is connected, you can send SMS from scripts or other apps using the server’s **3rd party API** with the **device credentials** shown in the app.

## 1. Get your device credentials

In the **SMS Gateway** Android app:

- Open **Settings** → **Cloud Server**
- After a successful connection you’ll see something like:
  - **Username:** e.g. `A1B2C3`
  - **Password:** e.g. `z9y8x7...`

Use this **Username** and **Password** for API auth (Basic auth for token, then Bearer token for sending).

## 2. API base URL

Use your Tailscale Serve URL with the 3rd party API path:

- **Base URL:** `https://stealth-dragon.tail793f98.ts.net/api/3rdparty/v1`

If that returns 404, try base URL **without** `/api`:  
`https://stealth-dragon.tail793f98.ts.net/3rdparty/v1`

## 3. Flow (two steps)

### Step A – Get a JWT token

- **Endpoint:** `POST /auth/token`
- **Auth:** Basic (Username = device username, Password = device password)
- **Body:** `{"scopes": ["messages:send"], "ttl": 86400}`

Example (replace `USER` and `PASS` with the app’s Username/Password):

```bash
curl -s -X POST "https://stealth-dragon.tail793f98.ts.net/api/3rdparty/v1/auth/token" \
  -u "USER:PASS" \
  -H "Content-Type: application/json" \
  -d '{"scopes": ["messages:send"], "ttl": 86400}'
```

Response contains `access_token`. Use it in the next step.

### Step B – Send an SMS

- **Endpoint:** `POST /messages`
- **Auth:** `Authorization: Bearer <access_token>`
- **Body:** `{"phoneNumbers": ["+79991234567"], "textMessage": {"text": "Hello from API!"}}`

Example (replace `TOKEN` with the `access_token` from step A):

```bash
curl -s -X POST "https://stealth-dragon.tail793f98.ts.net/api/3rdparty/v1/messages" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phoneNumbers": ["+79991234567"], "textMessage": {"text": "Hello from API!"}}'
```

Use E.164 format for numbers (e.g. `+79991234567`). Response is 202 with a `Location` header to check message status.

## 4. Optional: list devices

To see device IDs (e.g. to send only from a specific device):

```bash
curl -s "https://stealth-dragon.tail793f98.ts.net/api/3rdparty/v1/devices" \
  -H "Authorization: Bearer TOKEN"
```

You can pass `"deviceId": "..."` in the POST `/messages` body to target that device.

## 5. Web UI and Zapier

- **Web UI**: Open the Web UI (port 4842), enter device username, password, phone, and message. Credentials are not stored on the server.
- **Zapier**: Use the copy-pastable JavaScript block in [zapier/README.md](zapier/README.md) with variables `webuiUrl`, `username`, `password`, `phone`, `message`. Credentials are sent with each request.

## References

- [API overview](https://docs.sms-gate.app/integration/api/)
- [Authentication](https://docs.sms-gate.app/integration/authentication/)
- [OpenAPI spec](https://capcom6.github.io/android-sms-gateway/)
