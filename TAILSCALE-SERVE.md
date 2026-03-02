# SMS Gateway over Tailscale (HTTPS for Android)

Android blocks plain HTTP (CLEARTEXT). Use Tailscale Serve so the app connects over HTTPS.

## 1. Start Tailscale Serve on the server machine

From the machine where the SMS Gateway runs (e.g. stealth):

```bash
tailscale serve 4841
```

- First time: you may get a browser prompt to enable HTTPS for your tailnet — accept it.
- Note the URL it prints, e.g.:
  ```
  Available within your tailnet:
  https://stealth.your-tailnet.ts.net
  |-- / proxy http://127.0.0.1:4841
  ```
- Leave this terminal open, or run in background (see below).

## 2. API URL in the Android app

In **Settings → Cloud Server** use:

- **API URL:** `https://<that-hostname>/api/mobile/v1`  
  Example: `https://stealth.your-tailnet.ts.net/api/mobile/v1`  
  (no port — HTTPS uses 443)
- **Private Token:** (same as in `config.yml`)

Then turn **Cloud server** on and restart the app.

## Run Serve in the background (optional)

```bash
nohup tailscale serve 4841 > /tmp/tailscale-serve.log 2>&1 &
```

Or use a terminal multiplexer (tmux/screen) so you can reattach later.

---

## Troubleshooting

### "Failed to parse TLS packet header"

You're doing HTTPS to a server that only speaks HTTP (usually port 4841).

- **Wrong:** `https://100.x.x.x:4841/...` or `https://stealth:4841/...`
  Port 4841 is the app container — it's HTTP only. The app expects TLS and gets plain HTTP → parse error.

- **Right:** Use the **Tailscale Serve hostname with no port** so traffic goes to Tailscale's HTTPS (port 443), which then proxies to your app:
  - `https://stealth.your-tailnet.ts.net/api/mobile/v1`
  - No `:4841` — omit the port.

Check:

1. **Tailscale Serve is running** on the server machine: `tailscale serve 4841` (or in background).
2. **API URL in the app** is exactly: `https://<machine>.ts.net/api/mobile/v1` (the hostname printed by `tailscale serve 4841`, no port).
3. Phone and server are on the same Tailscale network and can reach each other.
