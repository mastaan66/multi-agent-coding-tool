# Contributing

Thank you for helping improve AI Software Factory.

## Before you start

- Search existing issues and discussions before opening a duplicate.
- Use an issue for large behavior changes so the design can be discussed first.
- Keep pull requests focused; unrelated cleanup should be separate.
- Never commit API keys, generated output projects, virtual environments, or release
  build directories.

## Development setup

~~~bash
git clone https://github.com/mastaan66/multi-agent-coding-tool.git
cd multi-agent-coding-tool
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
~~~

Run all local gates:

~~~bash
make quality
bash -n install.sh ai-factory.sh run.sh scripts/build_binary.sh scripts/render_demo.sh
~~~

Run the deterministic product demo:

~~~bash
./ai-factory.sh --demo "Build a todo API"
~~~

## Project conventions

- Python 3.10 is the minimum supported version.
- Add type hints to public functions and new core contracts.
- Use Pydantic models for structured agent and tool data.
- Preserve unrelated user changes.
- Treat model output as untrusted input.
- File and command safety must be enforced in code, not only prompts.
- Add deterministic tests for every bug fix.

## Pull requests

A pull request should include:

- a clear problem statement;
- the chosen approach and tradeoffs;
- tests or an explanation of why tests are not applicable;
- documentation changes for user-facing behavior;
- screenshots or regenerated media when terminal UX changes;
- passing CI.

Use concise conventional commit subjects where practical, for example:

~~~text
feat: add repository search tool
fix: reject symlink output escapes
docs: document standalone releases
~~~

## Release and media work

Build a local executable:

~~~bash
python -m pip install -e ".[release]"
make build
~~~

Regenerate README media:

~~~bash
make media
~~~

See [docs/RELEASING.md](docs/RELEASING.md) for the tagged release process.
