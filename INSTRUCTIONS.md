# Network Investigation Agent — Environment

This is a containerized Postgres + JupyterLab environment, pre-seeded with a network anomaly dataset (anomalies, device inventory, telemetry, and system logs), built for the Agentic AI take-home challenge.

Please follow the instructions below to set up and verify the environment. From there, refer to **`CHALLENGE.md`** for what to build.

# Setup Instructions

## Prerequisites

This environment requires a containerization engine.  Instructions are given below for Podman (preferred) and Docker; including installation instructions for the containerization engine.


### macOS

```bash
# Install Podman (recommended) or Docker
brew install podman podman-compose

# Alternative: Docker Desktop
# Download from https://www.docker.com/products/docker-desktop/
```

### Windows

Install [Podman Desktop](https://podman.io/docs/installation) (recommended)
Download from https://podman-desktop.io/downloads/windows
This will require

- Windows 11
- Hardware Virtualization be enabled in the bios
- Virtualization enabled in Windows (the installation page will provide instructions)
- Windows Subsystem for Linux (the installation page will provide instructions for this as well)

Setting up podman compose

- Open Podman Desktop, go to Settings > Resources.
- Find the Compose tile and click Setup.
- Follow the prompts to install the Compose engine and add podman-compose to your system's PATH.

**Alternative**: Docker Desktop

- Download from https://www.docker.com/products/docker-desktop/

## Quick Start

### macOS

```bash
cd agentic-ai-rca-challenge

# 1. Copy the env template and fill in whichever LLM key you're using
cp .env.example .env
# edit .env: set GOOGLE_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY

# 2. Build and start everything (Postgres + seeded data + JupyterLab)
podman-compose up -d --build

# using Docker instead
# docker compose -f podman-compose.yml  up -d --build

```

### Windows

Open PowerShell (or your preferred terminal, with Docker Desktop / Podman Desktop running):

```powershell
cd agentic-ai-rca-challenge

# 1. Copy the env template and fill in whichever LLM key you're using
copy .env.example .env
# edit .env: set GOOGLE_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY

# 2. Build and start everything (Postgres + seeded data + JupyterLab)
docker compose -f podman-compose.yml  up -d --build

# Using Podman instead:
# podman machine start   (if not already running)
# podman-compose -f podman-compose.yml up -d --build
```

First run takes a few minutes while the Jupyter image builds and Postgres loads the seed data. Give it 2-3 minutes before assuming something's wrong.

**Notes on installation issues:**

- The build doesn't always show a progress bar.
- **SSL/TLS errors behind a corporate proxy:** you can pre-pull the base image while ignoring SSL verification, then retry the build:

  ```bash
  # Docker
  docker pull --tls-verify=false jupyter/base-notebook:python-3.11
  # Podman
  podman pull --tls-verify=false jupyter/base-notebook:python-3.11
  ```

### LLM API Key

You also need an LLM to run your agent against. Use whatever you already have access to — there's no preferred provider. Options, roughly easiest-to-set-up first:

- **Google Gemini** — has a free tier with no payment method required. Steps:
  1. Go to https://aistudio.google.com/app/apikey (sign in with any Google account).
  2. Click **"Create API key"**, choose or create a Google Cloud project when prompted (a formality — no billing setup needed for the free tier), and copy the key.
  3. Put it in `.env` as `GOOGLE_API_KEY=...` (see Quick Start below).
- **OpenAI** — https://platform.openai.com/api-keys (`OPENAI_API_KEY`).
- **Anthropic** — https://console.anthropic.com/settings/keys (`ANTHROPIC_API_KEY`).
- **Open-source / self-hosted models** — also fine (e.g. [Ollama](https://ollama.com/) running locally, or the Hugging Face Inference API — https://huggingface.co/settings/tokens, free tier available). If you go this route, wire up the corresponding LangChain chat model class in your agent code yourself.

If none of this works for you, say so in your submission notes rather than spending your time budget on it.

## Access Points

- **JupyterLab**: http://localhost:8888 (no password/token required) — your working directory (`starter_code/`) is mounted at `work/` inside the container.
- **Adminer** (web DB browser): http://localhost:8081 — System: `PostgreSQL`, Server: `postgres`, Username: `rca_user`, Password: `rca_password`, Database: `network_rca`.
- **Postgres** (if connecting with your own client): `localhost:5432`, same credentials, database `network_rca`.

## Dataset Overview

| Table | Records | Description |
|---|---|---|
| `detected_anomalies` | 10 | Anomaly detector output |
| `network_devices` | 21 | Device inventory |
| `device_telemetry` | 25,704 | Hourly per-device metrics |
| `device_syslogs` | 2,322 | Device system logs |

## Verify Setup

1. Open http://localhost:8888 and open `work/notebooks/network_rca_agent.ipynb`.
2. Run the first three code cells. The first lists the 4 tables; the second prints their row counts; the third lists the 10 anomalies by date. You should see the 4 tables listed above, with matching row counts.

If you see this, your environment is ready — move on to `CHALLENGE.md`.

Note: the notebook's **last** cell (`build_graph()`) is expected to raise `NotImplementedError` on a fresh checkout — that's the stub you're about to implement, not a setup problem. Everything up to and including the anomaly-list cell should succeed.

# Additional Notes on Environment

## Environment Features

- **Postgres 16**, pre-seeded on first container start
- **JupyterLab** with LangGraph, LangChain, and LLM provider packages pre-installed
- **Adminer** for browsing the database without writing SQL by hand
- **Volume persistence** for notebooks and Postgres data across restarts

## File Structure

```
agentic-ai-rca-challenge/
├── CHALLENGE.md              # the actual challenge brief -- read this
├── INSTRUCTIONS.md           # this file
├── podman-compose.yml        # container orchestration (works with Docker or Podman)
├── Dockerfile                # JupyterLab image
├── .env.example               # copy to .env and fill in your LLM key
├── db/
│   ├── init/                  # schema + data-loading SQL (runs automatically)
│   └── seed/                  # seed CSVs
├── docs/
│   └── schema_reference.md    # database schema documentation
└── starter_code/
    ├── requirements.txt
    ├── db.py                   # Postgres query helper
    ├── main.py                 # minimal CLI entry point
    ├── agent/
    │   └── graph.py            # your agent implementation goes here
    └── notebooks/
        └── network_rca_agent.ipynb
```

## Where to Work

- Build your agent in `starter_code/agent/graph.py` (or add modules alongside it).
- Use `starter_code/notebooks/network_rca_agent.ipynb` and/or `starter_code/main.py` to run and demo it.
- `starter_code/db.py` is a ready-made Postgres helper — use it, wrap it, or replace it.
- Reference `docs/schema_reference.md` for the full data dictionary before you start writing tools.
- `starter_code/requirements.txt` already has everything needed for a complete solution. If you install anything beyond that, add it to `requirements.txt` with a pinned version (`pip freeze | grep <package>`) before submitting, so your submission is reproducible in a fresh container.

## Platform-Specific Notes

### macOS

- Docker Desktop and Podman both run a lightweight Linux VM under the hood; no extra configuration needed on your part either way.
- File permissions between the container and your Mac filesystem work without extra configuration.
- Use `podman machine start` if your Podman machine isn't already running.

### Windows

- Docker Desktop requires the WSL2 backend (the installer handles this); Podman Desktop requires the same.
- Podman Desktop provides its own GUI for managing containers/Compose if you prefer it to the terminal.
- Run commands from PowerShell or a WSL2 terminal — both work.
- File paths inside the containers use Unix-style paths (`/home/jovyan/...`); this is normal and doesn't require any action from you.

## Troubleshooting

> **A note on `podman-compose` vs `podman compose`:** there are two ways to drive
> Compose with Podman. `podman-compose` (hyphenated) is the standalone tool you
> installed via `brew install podman-compose` and is what this guide uses
> throughout. Newer Podman also ships a built-in `podman compose` (spaced)
> subcommand that delegates to a Compose provider. Either works against
> `podman-compose.yml`; pick one and use it consistently. Commands below use the
> hyphenated form; substitute `docker compose` if you're on Docker.

```bash
# Check container status
podman-compose ps
# or: docker compose -f podman-compose.yml  ps

# View logs (e.g. to confirm seed data loaded without errors)
podman-compose logs postgres
podman-compose logs jupyter
# or: docker compose -f podman-compose.yml  logs postgres / jupyter

# Restart
podman-compose restart
# or: docker compose -f podman-compose.yml  restart
```

**Port conflicts:** if 8888, 8081, or 5432 are already in use on your machine, edit the `ports:` section of `podman-compose.yml` (format is `"HOST_PORT:CONTAINER_PORT"` — only change the left-hand side). This applies whether you're using Docker or Podman.

**SSL/TLS errors on a corporate network:** see *Notes on installation issues* above.

**No local Docker/Podman / corporate machine restrictions:** contact your hiring contact — we'd rather adjust the setup than have that block you.

## Stop Environment

### macOS

```bash
# Stop containers
podman-compose stop
# or: docker compose -f podman-compose.yml stop

# Remove containers and volumes (clean slate)
podman-compose down -v
# or: docker compose -f podman-compose.yml  down -v
```

### Windows

```powershell
# Stop containers
podman-compose stop
# or: docker compose -f podman-compose.yml  stop

# Remove containers and volumes (clean slate)
podman-compose down -v
# or: docker compose -f podman-compose.yml  down -v
```

## When You're Done

Zip up this whole folder (including your code changes) and send it back to your contact, the same way this challenge was sent to you.
