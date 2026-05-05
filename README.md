# proxy-fleet

[中文文档](README_CN.md)

Manage multiple VPS proxy nodes from a single command line. Deploys [3x-ui](https://github.com/MHSanaei/3x-ui) + VLESS+Reality and generates a [Clash/Mihomo](https://github.com/MetaCubeX/mihomo) subscription URL that auto-updates when you add or remove nodes.

## Features

- **One-command deploy** — installs 3x-ui, picks an available port (scans for conflicts first), configures VLESS+Reality, opens the firewall, and updates your subscription file. All in one `deploy`.
- **Subscription sync** — queries every node's live API state and regenerates the Clash YAML, so the subscription always reflects reality.
- **NAT support** — pass `--nat 10000-10009` and it picks the first free port in that range.
- **Fleet status** — parallel health check across all nodes with traffic stats.
- **Modular rules** — AI services, streaming, general proxy, and China-direct rules in separate template files. Edit and `sync`.

## Requirements

- Python 3.8+ (stdlib only, no pip dependencies)
- SSH access to your VPS nodes (key-based auth via `~/.ssh/config`)
- `curl` on your local machine (for connectivity checks)
- VPS running Debian/Ubuntu (other distros may work but are untested)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/oaker-io/proxy-fleet.git
cd proxy-fleet

# 2. Interactive setup — creates config.json
python3 scripts/fleet.py init

# 3. Deploy to your first VPS
python3 scripts/fleet.py deploy my-vps --name "Tokyo" --emoji "🇯🇵"

# 4. Check status
python3 scripts/fleet.py status
```

## Commands

```
init                                    Interactive config setup
status                                  Show all nodes (parallel health check)
deploy <host> [host...]                 Deploy to one or more SSH hosts
deploy <host> --nat 10000-10009         Deploy on NAT machine with port range
deploy <host> --name "Name" --emoji "🇺🇸"  Deploy with custom display name
remove <host>                           Remove node from subscription
sync                                    Regenerate subscription from live state
```

## How It Works

### Deploy Flow

```
SSH connect → scan occupied ports → pick available port
  → install 3x-ui (if needed) → set panel credentials
  → generate x25519 keys → create VLESS+Reality inbound via API
  → detect firewall (ufw/iptables) → open ports
  → verify connectivity → save to config → sync subscription
```

### Subscription Hosting

The generated Clash YAML is uploaded to one of your VPS nodes via SSH. You serve it with nginx + SSL (e.g., behind Cloudflare). Users import the URL in Clash Verge Rev / Mihomo and get all nodes + routing rules.

### Proxy Groups

| Group | Purpose |
|-------|---------|
| 🤖 AI Services | OpenAI, Claude, Gemini, Copilot, Cursor, Midjourney, etc. — routes to US nodes first |
| 🚀 Proxy | Google, GitHub, Twitter, Telegram, Discord, etc. — routes to nearest nodes first |
| 🎬 Streaming | YouTube, Netflix, Spotify, Twitch |
| 🐟 Final | Catch-all fallback |

## File Structure

```
proxy-fleet/
├── config.json              # Your fleet state (gitignored — contains credentials)
├── config.example.json      # Template for new users
├── scripts/
│   └── fleet.py             # Main CLI script
└── templates/rules/
    ├── ai.yaml              # AI service routing rules
    ├── proxy.yaml           # Common proxy site rules
    ├── streaming.yaml       # Streaming service rules
    └── direct.yaml          # China-direct / LAN rules
```

## Updating Rules

Edit any file in `templates/rules/`, then:

```bash
python3 scripts/fleet.py sync
```

Users refresh their subscription in Clash Verge Rev to pick up the changes.

## Operational Safety

`proxy-fleet` is an operations tool and can change remote VPS state. Before deploying, make sure you understand the scope:

- `deploy` installs or reconfigures 3x-ui on the target host.
- `deploy` opens the selected VLESS port and the 3x-ui panel port when a restrictive firewall is detected.
- `deploy` only removes an existing VLESS inbound whose `remark` matches the node being deployed. It does **not** delete unrelated VLESS inbounds.
- `remove` only removes the node from local `config.json` and from the generated subscription. It does **not** uninstall 3x-ui, close firewall ports, or delete remote inbounds.
- `config.json` contains panel credentials and node state. It is gitignored and must not be committed.

## Verification

After any deploy or rule change:

```bash
python3 scripts/fleet.py status
python3 scripts/fleet.py sync
curl -I https://YOUR_SUBSCRIPTION_DOMAIN/YOUR_URL_PATH/config.yaml
```

Then refresh the subscription in Clash Verge Rev / Mihomo and test at least one proxied domain.

For remote troubleshooting:

```bash
ssh <host> 'systemctl status x-ui --no-pager'
ssh <host> 'ss -tlnp | grep -E "(:443|:9453)"'
```

## Development

The project intentionally keeps runtime dependencies to the Python standard library. Tests also use stdlib `unittest`:

```bash
python3 -m py_compile scripts/fleet.py
python3 -m unittest -v tests/test_fleet.py
```

## Tech Notes

- **Xray v26 key format**: `x25519` outputs `PrivateKey` / `Password` or `Password (PublicKey)` (= public key) / `Hash32`. Older versions use `Private key` / `Public key`. The script handles these variants.
- **3x-ui install script** is interactive and can't reliably receive piped input. We install with defaults, then reset credentials via the CLI.
- **3x-ui API**: `POST /login` → session cookie → `/panel/api/inbounds/{add,update,del,list}`. Newer 3x-ui may serve the panel via self-signed HTTPS; the script tries HTTPS first, then HTTP fallback.
- **Reality returns 400** to non-VLESS clients. The connectivity check treats 400 as "alive".
- **Port conflicts** are the #1 deploy failure. The script scans ports before configuring.
- **UFW detection** must match `Status: active`; do not use substring matching because `inactive` contains `active`.
- **Remote script args** are shell-quoted before passing through SSH, so node names and credentials may contain spaces or quotes.
- **DNS IPv6** is configurable with `defaults.dns.ipv6`; default is `false` for conservative client compatibility.

## License

[MIT](LICENSE)
