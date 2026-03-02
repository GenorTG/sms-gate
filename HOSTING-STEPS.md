# Hosting steps (fresh machine)

Strict order. Do not edit config or .env manually; the install script creates them.

---

## 1. Prerequisites

On the machine you will host on:

- Docker installed.
- Docker Compose installed (or the `docker compose` plugin).
- Git installed.

---

## 2. Clone the repo and enter it

```bash
git clone <REPO_URL> sms-gate
cd sms-gate
```

Replace `<REPO_URL>` with your repo URL (e.g. `https://github.com/your-org/sms-gate.git`).

---

## 3. Run the install script

```bash
./install-and-run-sms-gate-server.sh
```

The script will:

- If the SMS Gate stack is already running, ask whether to **redo install** (stop and remove containers and volumes, then reinstall with current code). Say `y` to refresh the stack after code changes.
- Generate a JWT secret and a private token (and write them into config).
- Ask for a database password (press Enter to use `root`).
- Create `config.yml` and `.env` (no manual editing). Device credentials are not stored; you send them with each request (Web UI or Zapier).
- Start the stack with `docker compose up -d` and wait until the server is up.
- Print the **private token** and next steps.

Save the private token shown at the end; you need it for the Android app. Do not skip this step or you will have to look it up in `config.yml` later.

---

## 4. Connect the Android app

- Open the SMS Gateway for Android app.
- Go to **Settings** → **Cloud Server**.
- Set **API URL** to your server URL + `/api/mobile/v1`:
  - Local/same LAN: `http://<THIS_MACHINE_IP>:3000/api/mobile/v1` (Android may block HTTP; use Tailscale or HTTPS if it fails.)
  - Tailscale: run `tailscale serve 3000` on this machine, then use `https://<machine>.ts.net/api/mobile/v1` (no port).
  - Production: `https://your-domain.com/api/mobile/v1` (reverse proxy to port 3000).
- Set **Private token** to the token the install script printed in step 3.
- Turn on **Cloud server** and restart the app if asked.
- After a successful connection, the app will show **Username** and **Password**. Use these in the Web UI or in API requests to send SMS; they are not stored on the server.

---

## 5. Verify

- **Web UI**: Open `http://<MACHINE_IP>:4842` (or your public URL). Enter the device **Username** and **Password** (from the app), plus **phone** and **message**; submit. The SMS should be sent. You can optionally check "Remember username/password in this browser" to store them only in your browser (localStorage).
- **API health**: On the server, run `curl http://localhost:3000/health/ready`; you should get JSON. The server also responds at `GET /` with version info.

---

## 6. Optional: expose for the Android app or Web UI

- **Tailscale**: On the server, run `tailscale serve 3000`. Use the shown HTTPS URL + `/api/mobile/v1` as the app API URL. For Web UI over Tailscale you can run another serve or use a different port.
- **Production**: Put a reverse proxy (e.g. Nginx/Caddy) in front with HTTPS. Proxy your domain to `http://localhost:3000` (API) and optionally to `http://localhost:4842` (Web UI).

---

## Troubleshooting: 404 on /api/mobile/v1 (production URL)

If your public URL (e.g. `https://sms-gate.rentiers.pl`) returns **200** for `GET /` (version JSON) and **200** for `GET /health/ready`, but **404** for `/api/mobile/v1` or `/api/3rdparty/v1`, the SMS Gateway server is **not mounting the API routes**. The proxy is forwarding correctly (the 404 body is from the server). Fix the server config so the API is under `/api`.

**1. Ensure the server mounts the API at `/api`**

The API path is controlled by `http.api.path` in `config.yml` or the `HTTP__API__PATH` environment variable. This repo’s `docker-compose.yml` sets `HTTP__API__PATH: /api`. If you deployed without it:

- **Using this repo:** Restart the stack so the server container gets `HTTP__API__PATH=/api` (already in `docker-compose.yml`), then try again.
- **Custom deploy:** Set env `HTTP__API__PATH=/api` for the server process, or ensure `config.yml` has `http.api.path: /api`.

**2. Check the backend on the server**

From the machine where Docker runs:

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/health/ready
curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:3000/api/mobile/v1/device -H "Content-Type: application/json" -d '{}'
```

- `GET /` and `GET /health/ready` should return `200`.
- `POST /api/mobile/v1/device` should return `401` or `400` (not `404`) if the API is mounted. If you get `404` here, the API is not mounted — fix step 1 and restart the server.

**3. Fix the reverse proxy (if API is mounted but public URL still 404)**

The app must receive the full path (e.g. `/api/mobile/v1`). Do **not** strip the path.

- **Nginx** — pass the full URI (no trailing slash on `proxy_pass`):

  ```nginx
  location / {
      proxy_pass http://127.0.0.1:3000;   # no trailing slash
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
  }
  ```

  If you use `proxy_pass http://127.0.0.1:3000/;` (with trailing slash), Nginx replaces the path and the backend gets the wrong path → 404.

- **Caddy** — simple reverse proxy:

  ```caddy
  sms-gate.rentiers.pl {
      reverse_proxy 127.0.0.1:3000
  }
  ```

**4. Android app API URL**

Use exactly:

- `https://sms-gate.rentiers.pl/api/mobile/v1`

No trailing slash. Path order matters: **`/api/mobile/v1`** (api → mobile → v1).  
Wrong (404): `/mobile/api/v1`, `/api/v1`, `/mobile/v1`.

**5. Nginx Proxy Manager (NPM)**

If you use Nginx Proxy Manager:

- Use a single **Proxy Host** for `sms-gate.rentiers.pl` → `127.0.0.1:3000` (or `host.docker.internal:3000` if NPM runs in Docker and the app is on the host). Do **not** use a “Redirect” — that sends the browser elsewhere.
- **Do not add “Custom locations”** for `/api` or `/api/mobile` unless you know you need them. A single proxy for `/` is enough; the backend expects the full path `/api/mobile/v1`.
- In **Advanced** → “Custom Nginx configuration”, **do not** add a `proxy_pass` with a trailing slash (e.g. `proxy_pass http://127.0.0.1:3000/;`). That would strip the path and cause 404 for `/api/mobile/v1`. Leave Advanced empty, or only add extra headers (e.g. `proxy_set_header ...`).
- WebSocket support (checkbox) is fine and does not change the path.

If 404 persists, open the proxy host in NPM, go to **Advanced**, and paste this so the full path is preserved (adjust upstream if needed):

```nginx
location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

If NPM runs in Docker and the SMS Gateway runs on the host, use `host.docker.internal:3000` instead of `127.0.0.1:3000` (or the host’s LAN IP). Then save and test `https://sms-gate.rentiers.pl/api/mobile/v1` again.

---

## Summary (strict order)

1. Prerequisites: Docker, Docker Compose, Git.
2. Clone repo; `cd sms-gate`.
3. Run `./install-and-run-sms-gate-server.sh`; save the printed private token.
4. Connect the Android app with the API URL and that private token; note the app’s Username and Password.
5. Verify: open the Web UI, enter Username, Password, phone, and message; send. Device credentials are not stored on the server.

No manual editing of `config.yml` or `.env` in the default path. The Web UI uses the internal URL `http://server:3000` automatically.
