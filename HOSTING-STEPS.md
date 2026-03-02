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

- **If the stack is already running:** offer **(U)pdate** (keep database, config, and .env; rebuild images and restart — no re-registering phones, no data loss), **(R)einstall** (remove everything and do a fresh install), or **(N)othing**.
- **If `config.yml` exists but the stack is not running:** offer **(S)tart** (bring up the existing stack), **(O)verwrite** (regenerate config and reinstall), or **(N)othing**.
- On a fresh install: generate a JWT secret and a private token (and write them into config).
- Ask for a database password (press Enter to use `root`).
- Ask for **Web UI admin username** (default: `admin`; press Enter to use it) and **password** (leave empty to disable Web UI login; set both to require login).
- Create `config.yml` and `.env`. When Web UI login is enabled, `WEBUI_SECRET_KEY` is generated and stored in `.env`.
- Start the stack with `docker compose up -d` and wait until the server is up.
- Print the **private token** and next steps.

**Updating:** Run the script again and choose **Update**. Your database, `config.yml`, `.env`, and registered devices stay intact; only images are rebuilt and containers restarted.

Save the private token shown at the end; you need it for the Android app. If you set a Web UI admin user, save that password; you will use it to log into the Web UI.

---

## 4. Connect the Android app

- Open the SMS Gateway for Android app.
- Go to **Settings** → **Cloud Server**.
- Set **API URL** to your server URL + `/api/mobile/v1`:
  - Local/same LAN: `http://<THIS_MACHINE_IP>:4841/api/mobile/v1` (Android may block HTTP; use Tailscale or HTTPS if it fails.)
  - Tailscale: run `tailscale serve 4841` on this machine, then use `https://<machine>.ts.net/api/mobile/v1` (no port).
  - Production: `https://your-domain.com/api/mobile/v1` (reverse proxy to port 4841).
- Set **Private token** to the token the install script printed in step 3.
- Turn on **Cloud server** and restart the app if asked.
- After a successful connection, the app will show **Username** and **Password**. Use these in the Web UI or in API requests to send SMS; they are not stored on the server.

---

## 5. Verify

- **Web UI**: Open `http://<MACHINE_IP>:4842` (or your public URL). If you set a Web UI admin user, log in first. Then set **Device account** (device username and password from the Android app) in the blue bar; this is used for Devices, Messages, Logs, Webhooks, Settings. Go to **Send SMS**, enter phone and message (device username is prefilled if set); submit. The SMS should be sent.
- **API health**: On the server, run `curl http://localhost:4841/health/ready`; you should get JSON. The server also responds at `GET /` with version info.

---

## 6. Optional: expose for the Android app or Web UI

- **Tailscale**: On the server, run `tailscale serve 4841`. Use the shown HTTPS URL + `/api/mobile/v1` as the app API URL. For Web UI over Tailscale you can run another serve or use a different port.
- **Production**: Put a reverse proxy (e.g. Nginx/Caddy) in front with HTTPS. Proxy your domain to `http://localhost:4841` (API) and optionally to `http://localhost:4842` (Web UI).

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
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4841/
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4841/health/ready
curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:4841/api/mobile/v1/device -H "Content-Type: application/json" -d '{}'
```

- `GET /` and `GET /health/ready` should return `200`.
- `POST /api/mobile/v1/device` should return `401` or `400` (not `404`) if the API is mounted. If you get `404` here, the API is not mounted — fix step 1 and restart the server.

**3. Fix the reverse proxy (if API is mounted but public URL still 404)**

The app must receive the full path (e.g. `/api/mobile/v1`). Do **not** strip the path.

- **Nginx** — pass the full URI (no trailing slash on `proxy_pass`):

  ```nginx
  location / {
      proxy_pass http://127.0.0.1:4841;   # no trailing slash
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
  }
  ```

  If you use `proxy_pass http://127.0.0.1:4841/;` (with trailing slash), Nginx replaces the path and the backend gets the wrong path → 404.

- **Caddy** — simple reverse proxy:

  ```caddy
  sms-gate.rentiers.pl {
      reverse_proxy 127.0.0.1:4841
  }
  ```

**4. Android app API URL**

Use exactly:

- `https://sms-gate.rentiers.pl/api/mobile/v1`

No trailing slash. Path order matters: **`/api/mobile/v1`** (api → mobile → v1).  
Wrong (404): `/mobile/api/v1`, `/api/v1`, `/mobile/v1`.

**5. Nginx Proxy Manager (NPM)**

If you use Nginx Proxy Manager:

- Use a single **Proxy Host** for your domain. **Forward hostname/port:** if NPM runs in Docker and the SMS Gateway runs on the same host, use `host.docker.internal` and port `4841` (or the host’s IP and port `4841`); if NPM and the stack are on the same host and NPM is not in Docker, use `127.0.0.1:4841`. Do **not** use a “Redirect”.
- **Do not add “Custom locations”** for `/api` or `/api/mobile`. Use **one** proxy that forwards **all** paths. If you have a Custom location that only matches `/`, other paths (e.g. `/health/ready`, `/api/mobile/v1`) may get NPM’s 404 or be sent to the wrong backend.
- In **Advanced** → “Custom Nginx configuration”, **do not** add a `proxy_pass` with a trailing slash (e.g. `proxy_pass http://127.0.0.1:4841/;`). That would strip the path. Leave Advanced empty, or only add extra headers.
- WebSocket support (checkbox) is fine.

If 404 persists, **see if the backend itself responds** (bypass NPM). On the machine where the SMS Gateway stack runs, run:

```bash
# Replace with your host’s IP if NPM and sms-gate are on the same host
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4841/
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4841/health/ready
curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:4841/api/mobile/v1/device -H "Content-Type: application/json" -d '{}'
```

- If **localhost returns 200 for `/` and `/health/ready` and 401 (not 404) for the POST**, the server is fine and the problem is NPM (e.g. Custom locations or wrong proxy). Fix NPM so the same request path is forwarded to `127.0.0.1:4841`.
- If **localhost also returns 404** for `/health/ready` or `/api/...`, the server is not mounting those routes. Recreate the server container so it gets `HTTP__API__PATH=/api`: from your repo directory (e.g. `cd /srv/data/services/sms-gate`) run `docker compose up -d --force-recreate server`, then test localhost again.

**NPM in Docker, SMS Gateway on the same host:** If localhost works but the public URL still returns 404, NPM is probably forwarding to the wrong target. From inside the NPM container, `127.0.0.1` is the container itself, not the host. In NPM, edit the Proxy Host and set **Forward hostname** to the host that runs the SMS Gateway:
- **`host.docker.internal`** (if available on your Docker setup), with port **4841**, or
- The host’s LAN IP (e.g. the machine’s IP on the Docker network or your LAN), with port **4841**.
Save and test the public URL again.

Optional NPM **Advanced** config to force full-path forwarding (use the same host as above):

```nginx
location / {
    proxy_pass http://host.docker.internal:4841;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

If `host.docker.internal` is not available (common on Linux), use the host’s IP address instead, e.g. `http://192.168.x.x:4841` or the gateway IP Docker uses to reach the host.

**Only root (`/`) works; `/health/ready` and `/api/*` return 404**

If you can open the public URL and see the version JSON at `/`, but `/health/ready` or `/api/mobile/v1` return 404 (with the server’s JSON body), the proxy is reaching the server but something is wrong with how other paths are handled.

- **Listen address:** The server must listen on `0.0.0.0:3000` so it accepts connections from the host and from the proxy. This repo’s `config.example.yml` and `docker-compose.yml` set `listen: 0.0.0.0:3000` and `HTTP__LISTEN: 0.0.0.0:3000`. Your `config.yml` (from the install script) keeps the same. So the server is exposed correctly.
- **Same backend for all paths:** In NPM you must have **one** Proxy Host that forwards **all** paths to the same backend (e.g. `host.docker.internal:4841` or the host IP). Do **not** add a “Custom location” that only forwards `/` or a subset of paths; that can make only the root hit the SMS Gateway and other paths hit nothing or another backend.
- **What path does the server see?** On the host, run `docker compose logs -f server` and in another terminal open `https://sms-gate.rentiers.pl/health/ready`. Check the server log line for that request: it usually shows the method and path. If the path is wrong (e.g. empty or different), the proxy is rewriting it. Fix NPM so the request path is sent unchanged.
- **Test with the same Host as the browser:** On the server host, run  
  `curl -v -H "Host: sms-gate.rentiers.pl" http://127.0.0.1:4841/health/ready`  
  If this returns 200, the server is fine and the issue is how NPM sends the request (path or Host). If this returns 404, the server may be routing by Host; then try without the Host header and compare.

---

## Summary (strict order)

1. Prerequisites: Docker, Docker Compose, Git.
2. Clone repo; `cd sms-gate`.
3. Run `./install-and-run-sms-gate-server.sh`; save the printed private token.
4. Connect the Android app with the API URL and that private token; note the app’s Username and Password.
5. Verify: open the Web UI, enter Username, Password, phone, and message; send. Device credentials are not stored on the server.

No manual editing of `config.yml` or `.env` in the default path. The Web UI uses the internal URL `http://server:3000` automatically.
