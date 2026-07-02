# Keel

The guiding structure for living software architecture. Keel is an open-source, self-hosted workspace for C4 diagrams, requirements, ADRs, quality characteristics, and agile delivery — all stored in your git repo and kept in sync with your code.

## What Keel does

Keel orchestrates the non-code phases of the SDLC inside your repository:

- **C4 architecture canvas** — Visualize and edit C1 (context), C2 (containers), and C3 (components) diagrams
- **Linked documentation** — Requirements, ADRs, and quality characteristics tied to architecture nodes
- **AI-assisted workflows** — Generate initial architecture, spar on design decisions, assess requirement impact, and generate work packages (via [Claude Code](https://code.claude.com/docs/en/setup))
- **Drift detection** — Map code changes to architecture nodes using path globs; optional GitHub Action for pull requests

All data lives under `.keel/` in your repo so architecture evolves with your codebase.

See [features/README.md](features/README.md) for shipped work packages, enhancements, and the roadmap.

## Prerequisites

| Requirement | Used for |
|-------------|----------|
| **Python 3.11+** | CLI and API server |
| **Git repository** | Keel stores architecture in-repo |
| **Claude Code CLI** (`claude`) | `keel init`, AI sparring, impact assessment, drift classification |
| **Node.js 18+** and **npm** | Building the UI bundle required for `keel dev` (from source) |

Install Claude Code and authenticate before running `keel init`:

```bash
# Install: https://code.claude.com/docs/en/setup
claude          # sign in interactively
# or for CI:
claude setup-token
```

Install Node.js and npm before running `keel dev` from a source checkout (the UI is not committed to git; you must build it once):

```bash
# Example with conda:
conda install -c conda-forge nodejs

# Verify:
node --version   # 18+
npm --version
```

## Installation

### Use Keel in your project

From PyPI (when published):

```bash
pip install keel
```

From source:

```bash
git clone https://github.com/zeezou17/keel.git
cd keel
pip install -e .
```

Verify the CLI:

```bash
keel --help
```

### Develop Keel itself

Clone the repo and install with dev dependencies:

```bash
git clone https://github.com/zeezou17/keel.git
cd keel
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Build the frontend bundle (required before `keel dev` will serve the UI):

```bash
./scripts/build_frontend.sh
```

This runs `npm install` and `npm run build` in `frontend/`, outputting static assets to `keel/static/`.

Run tests:

```bash
pytest
```

## Quick start

Keel runs against a **git repository**, not the Keel source tree itself. Initialise it in the project you want to document.

### 1. Initialise a workspace

From your project root:

```bash
cd /path/to/your-project
keel init
```

You will be prompted for a one-sentence system description. Press **Enter** without typing to analyse an existing codebase (brownfield). Provide a description for a greenfield project.

`keel init` will:

1. Verify the Claude Code CLI is installed and authenticated
2. Generate C1 and C2 architecture skeletons
3. Write files under `.keel/`
4. Merge agent context into `CLAUDE.md` and `.cursorrules`
5. Add a GitHub drift-check workflow and composite action
6. Create a git commit with the new files

Options:

```bash
keel init --path /path/to/repo          # initialise a different directory
keel init --description "My API service" # skip the prompt (via -d / --description)
```

### 2. Build the frontend (source installs only)

If you installed Keel from a git clone, build the UI bundle **before** starting the dev server:

```bash
cd /path/to/keel
./scripts/build_frontend.sh
```

This requires `npm` on your PATH. It runs `npm install` and `npm run build`, outputting static assets to `keel/static/`. Skip this step only if you installed a published package that already ships the built UI.

### 3. Start the dev server

```bash
keel dev
```

This starts the API and UI at [http://127.0.0.1:3141](http://127.0.0.1:3141) and opens it in your browser.

Options:

```bash
keel dev --port 8080       # custom port
keel dev --no-browser      # do not open a browser tab
keel dev --path /path/to/repo
```

## Using the UI

### Architecture canvas

- **Navigate C4 levels** — Click a system (C1) or container (C2) to drill into the next level. Use breadcrumbs to go back.
- **Add nodes** — Use **Add node** in the toolbar.
- **Edit nodes** — Select a node to open the detail panel. Update name, description, technology, and **path globs** that bind the node to source files.
- **Move nodes** — Drag nodes on the canvas; positions are saved automatically.
- **Commit** — Changes are written to `.keel/` immediately. Click **Commit** when the toolbar shows uncommitted changes to create a git commit.

### Sidebar: Requirements, ADRs, Characteristics

The left sidebar has three tabs:

- **Requirements** — Create and edit requirements (`REQ-*.md`). Link them to architecture nodes. Use **Assess impact** to ask Claude which nodes a requirement affects.
- **ADRs** — Architecture Decision Records (`ADR-*.md`) with status and links to nodes and characteristics.
- **Characteristics** — Quality attributes (`CHAR-*.yml`) with optional fitness functions (tests, lint rules, manual checks) used during drift detection.

Selecting a requirement highlights its linked nodes on the canvas.

### AI sparring

The sparring panel (right side) lets you discuss architecture with Claude in the context of the current C4 view. Suggested actions (such as adding nodes) can be applied directly to the diagram.

## Workspace layout

After `keel init`, your repo contains:

```
.keel/
├── architecture/
│   ├── c1-context.json       # C1 context diagram
│   ├── c2-containers.json    # C2 container diagram
│   └── c3-<container>.json   # C3 component diagrams (created on drill-down)
├── requirements/             # REQ-*.md
├── decisions/                # ADR-*.md
├── characteristics/          # CHAR-*.yml
└── specs/                    # WP-*.md work packages

.github/
├── workflows/keel-drift.yml
└── actions/keel-drift/action.yml

CLAUDE.md                     # Keel architecture context (merged section)
.cursorrules                  # Keel architecture context (merged section)
```

Architecture nodes include `paths` globs (e.g. `src/api/**`) that Keel uses to detect which files belong to which component.

## CLI reference

| Command | Description |
|---------|-------------|
| `keel init` | Initialise a Keel workspace in a git repo |
| `keel dev` | Start the local dev server and open the canvas (requires built UI in `keel/static/` when running from source) |

Both commands accept `--path` / `-p` to target a repository other than the current directory.

## Drift detection (GitHub Actions)

`keel init` installs a pull-request workflow that runs architecture drift checks. On each PR it:

1. Compares changed files against node path globs
2. Handles renames and auto-updates high-confidence path mappings
3. Uses Claude to classify unmapped files when needed
4. Evaluates quality-characteristic fitness functions for affected nodes
5. Posts a summary comment and sets an advisory check status

Configure a `CLAUDE_CODE_TOKEN` repository secret for AI classification in CI.

To fail the check when unmapped files remain, set `required: true` on the composite action:

```yaml
- uses: ./.github/actions/keel-drift
  with:
    required: "true"
  env:
    CLAUDE_CODE_TOKEN: ${{ secrets.CLAUDE_CODE_TOKEN }}
```

You can also run the drift check module directly in a GitHub Actions context:

```bash
python -m keel.action.drift_check
```

## API

The dev server exposes a REST API under `/api/` for architecture, requirements, ADRs, characteristics, git status, commits, sparring, impact assessment, and work-package generation. The React frontend in `frontend/` consumes these endpoints.

When developing the frontend separately:

```bash
cd frontend
npm install
npm run dev    # Vite dev server (API proxy may need configuration)
```

For production use, always build with `./scripts/build_frontend.sh` so `keel dev` serves the bundled UI from `keel/static/`.

## Agent integration

Keel merges a marked section into `CLAUDE.md` and `.cursorrules` pointing agents at `.keel/` files. Coding agents in Cursor or Claude Code can read architecture, requirements, and ADRs before making structural changes.

Keep node `paths` globs accurate when adding, moving, or renaming code so drift detection stays useful.

## License

AGPL-3.0-only — see [LICENSE](LICENSE).
