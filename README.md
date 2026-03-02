# SMS Gate

Self-hosted [SMS Gateway for Android](https://docs.sms-gate.app/) private server plus a minimal Web UI and Zapier-friendly API for sending SMS.

- **SMS Gateway**: Android app connects here; you send/receive SMS via the API.
- **Web UI**: Simple form (phone + message) on port 4842; credentials from env.
- **Zapier**: POST to `/api/send` with `{"phone":"+...","message":"..."}` (see [zapier/README.md](zapier/README.md)).
- **CLI**: [send-sms.sh](send-sms.sh) for interactive or scripted sending.

## Quick start

**On a fresh machine:** clone the repo, `cd` into it, then run:

```bash
./install-and-run-sms-gate-server.sh
```

The script generates secrets, creates `config.yml` and `.env`, starts the stack, and prints a **private token**. Use that token in the Android app (Settings → Cloud Server). After the app connects and shows Username and Password, run:

```bash
./install-and-run-sms-gate-server.sh --set-credentials
```

and enter those credentials so the Web UI can send SMS. No manual editing of config or .env needed.

**Manual setup (alternative):**

1. Copy `config.example.yml` to `config.yml`; set database password, `gateway.private_token`, and `jwt.secret` (e.g. `openssl rand -base64 32`).
2. Create `.env` with `DB_PASSWORD`, `SMS_GATE_USER`, and `SMS_GATE_PASS` (device credentials from the app after it connects).
3. Run `docker compose up -d`. API: http://localhost:3000, Web UI: http://localhost:4842.

## Project layout

| Path | Description |
|------|-------------|
| `install-and-run-sms-gate-server.sh` | Interactive install: creates config and .env, starts stack; use `--set-credentials` after the app connects |
| `docker-compose.yml` | db, server (sms-gate), worker, webui |
| `config.yml` | Server config (not in git; created by install script or from `config.example.yml`) |
| `send-sms.sh` | CLI to send SMS (interactive or with env/args) |
| `webui/` | Flask app: form + `POST /api/send` for Zapier |
| `zapier/README.md` | Copy-pastable Zapier blocks |

## Web UI (port 4842)

- **GET /** – Form: phone number (E.164) and message. Submit sends via the sms-gate API using `SMS_GATE_USER` / `SMS_GATE_PASS`.
- **POST /api/send** – JSON body: `{"phone": "+...", "message": "..."}`. Same credentials from env; returns JSON success/error.

Set `SMS_GATE_USER` and `SMS_GATE_PASS` in the environment (e.g. in `.env` for `docker compose`). Do not commit `.env` or `config.yml`.

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
