# EcoFlow Keep-Alive

[![Publish Docker Image](https://github.com/nielshh/ecoflow-keepalive/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/nielshh/ecoflow-keepalive/actions/workflows/docker-publish.yml)
[![Container Registry](https://img.shields.io/badge/ghcr.io-ecoflow--keepalive-blue?logo=docker)](https://github.com/nielshh/ecoflow-keepalive/pkgs/container/ecoflow-keepalive)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Project Page](https://img.shields.io/badge/docs-GitHub%20Pages-informational)](https://nielshh.github.io/ecoflow-keepalive/)

A lightweight headless Chromium Docker container that keeps the EcoFlow web portal active so Home Assistant EcoFlow integrations continue receiving live cloud MQTT telemetry without going stale.

## Why this exists

Some EcoFlow devices and cloud integrations stop publishing real-time MQTT telemetry after a while unless an authenticated EcoFlow portal/app session stays active. Running this small container signs into your EcoFlow user portal in headless Chromium, disables CSS animations to minimize CPU usage, watches for browser page crashes, and cleanly restarts on a configurable schedule (every 4 hours by default) so the session stays fresh.

## Features

- **Multi-architecture GHCR image**: Ready to run on `linux/amd64` and `linux/arm64` (Raspberry Pi, Mac mini, Synology NAS, x86 servers).
- **Automatic scheduled refresh**: Cleanly exits after `RESTART_INTERVAL_HOURS` (default `4` hours) so Docker (`restart: unless-stopped`) brings up a fresh Chromium session.
- **Crash recovery**: Uses `shm_size: 512mb`, Docker-safe Chromium flags, and a `crash` listener to catch renderer crashes immediately instead of hanging.
- **Low CPU overhead**: Injects CSS on load to disable animations and transitions.
- **Configurable**: Supports custom portal regions (`ECOFLOW_REGION`), optional country dropdown selection (`ECOFLOW_COUNTRY`), optional debug screenshots, and graceful `SIGTERM`/`SIGINT` handling.

## Quick Start

### Docker Compose (recommended)

Create a `docker-compose.yml` file:

```yaml
services:
  ecoflow-keepalive:
    image: ghcr.io/nielshh/ecoflow-keepalive:latest
    container_name: ecoflow-keepalive
    init: true
    shm_size: "512mb"
    restart: unless-stopped
    environment:
      - ECOFLOW_EMAIL=your-email@example.com
      - ECOFLOW_PASSWORD=your-password
      # Optional:
      # - ECOFLOW_REGION=eu
      # - ECOFLOW_COUNTRY=Netherlands
      # - RESTART_INTERVAL_HOURS=4
      # - DEBUG_SCREENSHOTS=false
```

Start the container:

```bash
docker compose up -d
```

View logs:

```bash
docker compose logs -f
```

### Docker Run

```bash
docker run -d \
  --name ecoflow-keepalive \
  --init \
  --shm-size=512mb \
  --restart unless-stopped \
  -e ECOFLOW_EMAIL="your-email@example.com" \
  -e ECOFLOW_PASSWORD="your-password" \
  ghcr.io/nielshh/ecoflow-keepalive:latest
```

## Configuration

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `ECOFLOW_EMAIL` | Yes | — | EcoFlow account email address. |
| `ECOFLOW_PASSWORD` | Yes | — | EcoFlow account password. |
| `ECOFLOW_REGION` | No | `eu` | EcoFlow portal URL region segment (`https://user-portal.ecoflow.com/user/<region>/en/login`, e.g. `eu`, `us`). |
| `ECOFLOW_COUNTRY` | No | *(empty)* | Optional country name to pick from the login country dropdown if it does not match the default selection (e.g. `Netherlands`). |
| `RESTART_INTERVAL_HOURS` | No | `4` | Hours to keep the dashboard open before exiting for a clean Docker restart. |
| `DEBUG_SCREENSHOTS` | No | `false` | Set to `true` to save pre-login, failure, and dashboard screenshots into `SCREENSHOT_DIR`. |
| `SCREENSHOT_DIR` | No | `/app/output` | Directory inside the container where debug screenshots are written when `DEBUG_SCREENSHOTS=true`. |
| `ECOFLOW_USER_AGENT` | No | *(Chromium default)* | Optional custom browser User-Agent string. |

## Building Locally

If you prefer building the image yourself instead of pulling from GHCR:

```bash
git clone https://github.com/nielshh/ecoflow-keepalive.git
cd ecoflow-keepalive
```

Edit [docker-compose.yml](docker-compose.yml) to uncomment `build: .` and comment out `image:`, set your credentials, and run:

```bash
docker compose up -d --build
```

## Troubleshooting

- **`Page.goto: Page crashed` in Docker**: Make sure `shm_size: "512mb"` (or `--shm-size=512mb`) is configured. Docker's default 64 MB `/dev/shm` is too small for Chromium.
- **Login stays on `/login`**: Double-check your `ECOFLOW_EMAIL`, `ECOFLOW_PASSWORD`, and `ECOFLOW_REGION` (or `ECOFLOW_COUNTRY`). Temporarily set `DEBUG_SCREENSHOTS=true` and mount `- ./output:/app/output` to inspect `screenshot_before_click.png` and `screenshot_failed.png`—and remove those screenshots afterward since they contain account info.

## Disclaimer

This is an unofficial community utility and is not affiliated with, endorsed by, or supported by EcoFlow. Use at your own risk and handle your account credentials securely.

## License

Released under the [MIT License](LICENSE).
