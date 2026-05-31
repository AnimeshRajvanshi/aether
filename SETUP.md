# Setup — first time on macOS

This walks you from a fresh Mac mini to a working Aether dev environment with the Sprint 1 ontology installed and tests passing.

Total time: ~20 minutes, mostly waiting for installers.

---

## 1. Install Homebrew (if you don't have it)

Open Terminal and paste:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

After it finishes, follow the on-screen instructions to add Homebrew to your PATH (usually two `echo` commands it prints for you).

Verify:

```bash
brew --version
```

## 2. Install the core tools

```bash
brew install git uv node pnpm
brew install --cask docker
```

- `git` — version control
- `uv` — fast Python package manager and project tool (replaces pip + venv + pyenv)
- `node` and `pnpm` — for the frontend later
- `docker` — for Postgres+PostGIS when we get to the data spine

Verify:

```bash
git --version
uv --version
node --version
pnpm --version
```

Open Docker Desktop once after install so it can initialize. You don't need to do anything in it yet.

## 3. Install Claude Code

This is the single best leverage move for this project. Claude Code runs in your terminal, can read and write your code, and execute commands, so you stop being a copy-paste intermediary.

```bash
npm install -g @anthropic-ai/claude-code
```

Then in any directory:

```bash
claude
```

The first run will walk you through authentication.

## 4. Create the GitHub repository

In a browser, go to https://github.com/new and create a new private repository:

- Owner: your account
- Repository name: `aether`
- Description: *AI-native dashboard and analysis engine for orbital and planetary monitoring data.*
- Visibility: **Private** (we'll decide on open-source later)
- Do **not** initialize with README, .gitignore, or license — we already have those

Click "Create repository." On the next page, copy the URL (something like `git@github.com:<your-username>/aether.git`).

## 5. Drop in the Sprint 1 skeleton

Download the `aether_sprint1.zip` archive (presented alongside this file). Then:

```bash
cd ~/Developer    # or wherever you keep code; create the dir if it doesn't exist
unzip ~/Downloads/aether_sprint1.zip
cd aether
```

Initialize git and connect to GitHub:

```bash
git init
git branch -M main
git add .
git commit -m "Sprint 1: ontology v0.1 + repo skeleton"
git remote add origin git@github.com:<your-username>/aether.git
git push -u origin main
```

If git asks about SSH keys you don't have set up yet, GitHub has a one-page guide: https://docs.github.com/en/authentication/connecting-to-github-with-ssh

## 6. Install Python dependencies and run the tests

From inside the `aether/` directory:

```bash
uv sync
uv run pytest packages/ontology -v
```

You should see **20 tests pass.** If you don't, copy the output and we'll fix it.

## 7. Confirm everything works

```bash
uv run python -c "
from datetime import datetime, timezone
from aether_ontology import Observation, SensorType, Provenance, GeoJSONGeometry, TimeRange

obs = Observation(
    sensor='EMIT',
    sensor_type=SensorType.HYPERSPECTRAL,
    granule_id='EMIT_L2B_CH4ENH_001_TEST',
    time_range=TimeRange(start=datetime(2024, 6, 15, 18, 30, tzinfo=timezone.utc)),
    footprint=GeoJSONGeometry(type='Point', coordinates=[-102.5, 31.8]),
    provenance=Provenance(source='EMIT L2B v1', source_id='EMIT_L2B_CH4ENH_001_TEST'),
)
print(obs.model_dump_json(indent=2))
"
```

If that prints a properly-formatted Observation JSON, you're ready for Sprint 1 items 3-5 (eval harness, benchmark seed, EMIT proof-of-life).

---

## What to do next

Once you've got tests passing locally and pushed to GitHub, come back here and I'll walk you through the next three items in Sprint 1:

- **Eval harness skeleton** (`/eval/harness`)
- **Benchmark seed** — 5 Carbon Mapper public events ingested as data
- **EMIT proof-of-life** — pull a real granule, render the plume on a static map

After that we hit the Sprint 1 gate.
