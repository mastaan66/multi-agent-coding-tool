# 🏭 AI Software Factory

> **Multiple specialized AI agents collaborating like a real engineering team.**

This system simulates a complete software development lifecycle using specialized AI agents. Each agent has a narrow role — planning architecture, writing code, reviewing, improving, testing, and preparing deployment — creating an iterative improvement pipeline that produces higher-quality code than a single LLM call.

## Architecture

```
User Request
     │
     ▼
┌─────────────────────────────────────┐
│         Pipeline Orchestrator       │
│                                     │
│  Planner → Coder → Reviewer  ─┐     │
│                          ↕    │     │
│                      Improver─┘     │
│                          │          │
│  Deployer ← Test Runner ←┘          │
│                    ↕                │
│                 Improver            │
└─────────────────────────────────────┘
     │
     ▼
  output/<project>/
```

### Agents

| Agent | Role | What It Does |
|-------|------|-------------|
| **Planner** | Software Architect | Designs architecture, file structure, API contracts |
| **Coder** | Software Engineer | Writes complete, production-ready code |
| **Reviewer** | Code Reviewer | Finds bugs, security issues, bad patterns |
| **Improver** | Improvement Specialist | Fixes all issues from review |
| **Tester** | QA Engineer | Writes comprehensive pytest suites |
| **Test Runner** | QA Analyst | Runs tests, analyzes failures, suggests fixes |
| **Deployer** | DevOps Engineer | Creates Dockerfile, CI/CD, deployment configs |

### Iterative Loops

- **Review → Improve**: Up to 3 iterations until code quality is satisfactory
- **Test → Fix**: Up to 3 iterations until all tests pass

## Quick Start

### Option A: One-Command Launch (Recommended)

```bash
cd Multi-Agent
./run.sh
```

This auto-creates a virtualenv, installs deps, and launches the interactive app.

### Option B: Manual Setup

```bash
cd Multi-Agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python3 -m src.main
```

### What Happens

1. **Paste your API key** — auto-saved to `.env` *(or leave blank for Demo Mode!)*
2. **Pick a model** — GPT-4o, 4o-mini, 4.1, 4.1-mini, or 4.1-nano
3. **Describe your project** — tell the AI team what to build
4. **Watch the agents work** — live spinners show each stage
5. **Get your project** — complete code in `output/`

> **Note on Demo Mode:** If you press enter without an API key, the app runs a deterministic offline simulation and generates a self-contained FastAPI Todo project that demonstrates the complete output format.

### Direct Mode (Power Users)

```bash
python3 -m src.main "Create a REST API for a todo app"
```

### Output

Generated projects are written to `output/<project_name>_<timestamp>/` with:
- All source code files
- Test suite
- Dockerfile & docker-compose.yml
- GitHub Actions CI/CD pipeline
- `DEPLOYMENT.md` with instructions

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Your OpenAI API key |
| `OPENAI_MODEL_NAME` | `gpt-4o` | LLM model to use |
| `OPENAI_TEMPERATURE` | `0.2` | Creativity level (0-1) |
| `MAX_REVIEW_ITERATIONS` | `3` | Max review-improve cycles |
| `MAX_TEST_FIX_ITERATIONS` | `3` | Max test-fix cycles |
| `OUTPUT_DIR` | `output` | Where to write projects |

## Development

Install the development tools and run the local quality gates:

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy
pytest
```

## Project Structure

```
Multi-Agent/
├── pyproject.toml          # Dependencies & project config
├── .env.example            # Configuration template
├── README.md
├── src/
│   ├── main.py             # CLI entry point
│   ├── core/
│   │   ├── config.py       # Settings management
│   │   ├── models.py       # Shared data models
│   │   └── pipeline.py     # Orchestration engine
│   ├── agents/
│   │   ├── planner.py      # Architect agent
│   │   ├── coder.py        # Code generator agent
│   │   ├── reviewer.py     # Code reviewer agent
│   │   ├── improver.py     # Code improver agent
│   │   ├── tester.py       # Test generator agent
│   │   ├── test_runner.py  # Test runner agent
│   │   └── deployer.py     # Deployment agent
│   └── tools/
│       ├── file_writer.py  # Safe file writer
│       └── code_executor.py # Sandboxed code executor
└── output/                 # Generated projects
```

## Development Roadmap

The project is evolving from a fixed greenfield generator into a safe,
repository-aware coding agent with interactive sessions, approvals, sandboxed
commands, checkpoints, provider adapters, MCP, hooks, and optional parallel
agents.

See the detailed [product and engineering roadmap](docs/ROADMAP.md).

## License

MIT
