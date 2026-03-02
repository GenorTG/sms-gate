# SMS Gate

Self-hosted [SMS Gateway for Android](https://docs.sms-gate.app/) private server plus a minimal Web UI and Zapier-friendly API for sending SMS.

- **SMS Gateway**: Android app connects here; you send/receive SMS via the API.
- **Web UI**: Form (device username, password, phone, message) on port 4842; credentials are not stored on the server.
- **Zapier**: Copy-pastable JavaScript block (see [zapier/README.md](zapier/README.md)): set Web UI URL, device username, password, phone, and message in Zapier; credentials sent with each request.

## Quick start

**On a fresh machine:** clone the repo, `cd` into it, then run:

```bash
./install-and-run-sms-gate-server.sh
```

The script generates secrets, creates `config.yml` and `.env`, starts the stack, and prints a **private token**. Use that token in the Android app (Settings → Cloud Server). To send SMS, open the Web UI and enter the device Username and Password (from the app) plus phone and message; credentials are not stored on the server.

**Manual setup (alternative):**

1. Copy `config.example.yml` to `config.yml`; set database password, `gateway.private_token`, and `jwt.secret` (e.g. `openssl rand -base64 32`).
2. Create `.env` with `DB_PASSWORD` (for compose). Device credentials are not stored; enter them in the Web UI or in each API request.
3. Run `docker compose up -d`. API: http://localhost:3000, Web UI: http://localhost:4842.

## Project layout

| Path | Description |
|------|-------------|
| `install-and-run-sms-gate-server.sh` | Interactive install: creates config and .env, starts stack; device credentials are entered in the Web UI |
| `docker-compose.yml` | db, server (sms-gate), worker, webui |
| `config.yml` | Server config (not in git; created by install script or from `config.example.yml`) |
| `webui/` | Flask app: form + `POST /api/send`; Zapier uses the same API with a JS block |
| `zapier/README.md` | Copy-pastable Zapier blocks |

## Web UI (port 4842)

- **GET /** – Form: (1) Device username and password (from Android app), with optional "Save in this browser for next time" (localStorage only); (2) Phone (E.164) and message. Credentials are not stored on the server. Served with gunicorn in production (no dev-server warning).
- **POST /api/send** – JSON body: `{"username": "...", "password": "...", "phone": "+...", "message": "..."}`. All four required; credentials are used only for that request. Returns JSON success/error.

## Production

- Run behind a reverse proxy (e.g. Nginx/Caddy) with HTTPS.
- Use a subdomain (e.g. `https://sms.yourcompany.com`) for the Web UI and/or the sms-gate API as needed.
- Keep `config.yml` and `.env` out of version control; use `config.example.yml` as reference.

## Docs

- [SEND-SMS-API.md](SEND-SMS-API.md) – API usage and send flow.
- [TAILSCALE-SERVE.md](TAILSCALE-SERVE.md) – Tailscale HTTPS for the Android app.
- [zapier/README.md](zapier/README.md) – Zapier webhook and direct API blocks.

## License

SMS Gateway for Android is under its own license. This repo’s additions (Web UI, scripts, docs) are for use with that project.
