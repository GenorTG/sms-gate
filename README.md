# SMS Gate

Self-hosted [SMS Gateway for Android](https://docs.sms-gate.app/) private server plus a **full Web UI control layer** and Zapier-friendly API.

- **SMS Gateway**: Android app connects here; you send/receive SMS via the API.
- **Web UI** (port 4842): Admin login (optional), then Dashboard, Send SMS, Devices, Messages, Logs, Webhooks, Settings, Health. Set "Device account" (sms-gate credentials from the app) in the Web UI to use API-backed pages. Credentials are stored only in your session.
- **Zapier**: `POST /api/send` remains public; see [zapier/README.md](zapier/README.md).

## Quick start

**On a fresh machine:** clone the repo, `cd` into it, then run:

```bash
./install-and-run-sms-gate-server.sh
```

The script generates secrets, creates `config.yml` and `.env`, starts the stack, and prints a **private token**. Use that token in the Android app (Settings → Cloud Server). To send SMS, open the Web UI and enter the device Username and Password (from the app) plus phone and message; credentials are not stored on the server.

**Updating an existing install:** Run `./install-and-run-sms-gate-server.sh` and choose **Update (U)**. Database, config, and .env are kept; only images are rebuilt and containers restarted (no re-registering phones or losing SMS history).

**Manual setup (alternative):**

1. Copy `config.example.yml` to `config.yml`; set database password, `gateway.private_token`, and `jwt.secret` (e.g. `openssl rand -base64 32`).
2. Create `.env` with `DB_PASSWORD`. Optionally set `WEBUI_ADMIN_USER`, `WEBUI_ADMIN_PASSWORD`, and `WEBUI_SECRET_KEY` (e.g. `openssl rand -hex 24`) to enable Web UI login.
3. Run `docker compose up -d`. API: http://localhost:4841, Web UI: http://localhost:4842.

## Project layout

| Path | Description |
|------|-------------|
| `install-and-run-sms-gate-server.sh` | Interactive install: creates config and .env, starts stack; device credentials are entered in the Web UI |
| `docker-compose.yml` | db, server (sms-gate), worker, webui |
| `config.yml` | Server config (not in git; created by install script or from `config.example.yml`) |
| `webui/` | Flask app: admin auth, Dashboard, Send SMS, Devices, Messages, Logs, Webhooks, Settings, Health; `POST /api/send` public for Zapier |
| `zapier/README.md` | Copy-pastable Zapier blocks |

## Web UI (port 4842)

- **Login**: If `WEBUI_ADMIN_USER` and `WEBUI_ADMIN_PASSWORD` are set, you must log in first. Set `WEBUI_SECRET_KEY` when using auth.
- **Device account**: After login, set the "Device account" (sms-gate device username/password from the Android app) to use Devices, Messages, Logs, Webhooks, Settings. Stored in session only.
- **Pages**: Dashboard, Send SMS, Devices (list/remove), Messages (list/detail/enqueue), Logs (from/to filter), Webhooks (list/add/delete), Settings (view/patch), Health.
- **POST /api/send** – Public; JSON body: `{"username": "...", "password": "...", "phone": "+...", "message": "..."}`. For Zapier/scripts; credentials sent per request.

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
