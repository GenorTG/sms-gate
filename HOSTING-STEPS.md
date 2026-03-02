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
- **API health**: On the server, run `curl http://localhost:3000/health`; you should get JSON.

---

## 6. Optional: expose for the Android app or Web UI

- **Tailscale**: On the server, run `tailscale serve 3000`. Use the shown HTTPS URL + `/api/mobile/v1` as the app API URL. For Web UI over Tailscale you can run another serve or use a different port.
- **Production**: Put a reverse proxy (e.g. Nginx/Caddy) in front with HTTPS. Proxy your domain to `http://localhost:3000` (API) and optionally to `http://localhost:4842` (Web UI).

---

## Summary (strict order)

1. Prerequisites: Docker, Docker Compose, Git.
2. Clone repo; `cd sms-gate`.
3. Run `./install-and-run-sms-gate-server.sh`; save the printed private token.
4. Connect the Android app with the API URL and that private token; note the app’s Username and Password.
5. Verify: open the Web UI, enter Username, Password, phone, and message; send. Device credentials are not stored on the server.

No manual editing of `config.yml` or `.env` in the default path. The Web UI uses the internal URL `http://server:3000` automatically.
