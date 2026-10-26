# Invite a friend to the local demo

LedgerX remains on your Mac: React and FastAPI run in the app container, PostgreSQL keeps the data
in `.runtime/postgres`. An optional Cloudflare Quick Tunnel supplies a temporary HTTPS address.
It works for a friend on another network as well as someone on your Wi-Fi. No cloud server,
domain purchase, Cloudflare account or global installation is needed for this development tunnel.
See [Cloudflare's Quick Tunnel documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## Start sharing

After the successful local release, with Docker Desktop running, execute from LedgerX:

```bash
bash scripts/share_local.sh
```

Docker downloads the pinned `cloudflare/cloudflared:2026.10.3` image if missing. The script starts
the existing app/database containers, checks readiness, then runs a separate foreground tunnel.
It does not rebuild your app or recreate your administrator. The base Compose file continues to
bind ports to loopback; the opt-in `compose.share.yaml` adds only the connector.

Find the `https://...trycloudflare.com` address in the terminal and send that address to your friend.
Do not send `127.0.0.1`: that refers to the computer of whoever opens it. HTTPS is also required for
the browser's secure payment-key generation outside localhost.

Anyone with the link can reach the demo's signup page. Existing ownership checks still protect
each user's accounts. Use distinct demo credentials; never give your friend your administrator
password. The tunnel provider terminates browser HTTPS and relays application traffic to your Mac.
This shares the existing local demo, not a separate database copy.

## Your friend's first transaction

1. Open the HTTPS link and select **Create account** to register a new customer login.
2. Open a financial account in EUR. It starts with a zero balance.
3. Copy that account's identifier from the interface and send it to you.
4. You sign in with your existing administrator. If needed, use **Add demo funds** on your own
   account, then send a transfer to your friend's account identifier. Funding must be enabled;
   the successful release used `ENABLE_DEV_FUNDING=true`.
5. Your friend can inspect the incoming transfer, send money to another account or return an
   eligible received transfer through its payment details. No terminal or Docker installation
   is needed on your friend's computer.

Registration creates a normal customer, never an administrator. Profiles, financial accounts and
money persist in your PostgreSQL database. A browser reload requires signing in again because
the frontend keeps its token in memory.

### Keep demo funding enabled across local restarts

If the administrator cannot see **Add demo funds**, add or update this line in the project's
ignored `.env` file, preserving the other settings:

```dotenv
ENABLE_DEV_FUNDING=true
```

Apply the configuration with `docker compose up -d app`, then sign out and sign back in so the
browser reloads the account's capabilities. Confirm the running container setting with
`docker compose exec app printenv ENABLE_DEV_FUNDING`. A shell prefix such as
`ENABLE_DEV_FUNDING=true docker compose up -d app` applies to that command only; a later
`docker compose up` without that prefix reads `.env` or falls back to the default `false`.
The repository's default remains disabled, and ordinary customers still cannot issue funds.

## Stop and restart sharing

Press **Ctrl+C** in the sharing terminal. The temporary tunnel container exits and is removed;
your app and database stay running locally. If the terminal was closed unexpectedly, inspect and
stop any remaining connector without stopping the app:

```bash
docker compose -p ledgerx -f compose.yaml -f compose.share.yaml ps --all
docker compose -p ledgerx -f compose.yaml -f compose.share.yaml stop share
```

The next sharing session receives a different hostname. Your Mac must remain awake and connected,
with Docker and the tunnel running. Quick Tunnels have no uptime guarantee and support at most
200 in-flight requests; that is a provider limit, not 200 supported LedgerX users. They do not
support SSE. See [provider limits](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/#limitations).
Several visitors can share the existing authentication rate budget because forwarded headers
are not trusted; wait for `Retry-After` on a 429.

## Verification boundary

The underlying app passed 149 backend, 26 frontend and 12 browser tests in the 22 October local
release. Syntax and merged Compose configuration passed; four simulated command-control checks
covered an unavailable engine, failed container query, missing app and valid command sequencing.
On 26 October, the actual helper restarted the existing healthy containers, passed its local API
check, downloaded `cloudflare/cloudflared:2026.10.3`, and registered a Quick Tunnel. Cloudflare's
DNS, QUIC, HTTP/2 and API prechecks all passed.

Later on 26 October, the project owner reported that a friend could access the app and complete
transfers from another computer through the tunnel. The owner then supplied an administrator
reconciliation screenshot checked at **23:27:58 local time**, showing **Everything balances**:
7 accounts, 8 transfers and 16 journal entries, with no balance modifications. This is a manual
observation reported by the owner, separate from the automated test results. An external refund
was not explicitly reported. No cloud-hosted deployment or uptime guarantee is claimed.
