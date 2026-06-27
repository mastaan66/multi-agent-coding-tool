# Installation

## Standalone release binary

The recommended end-user installation on Linux and macOS is the checksum-verifying
installer:

~~~bash
curl -fsSL https://raw.githubusercontent.com/mastaan66/multi-agent-coding-tool/main/install.sh | sh
~~~

The default destination is ~/.local/bin. Override it with:

~~~bash
AI_FACTORY_INSTALL_DIR=/usr/local/bin sh install.sh
~~~

Install a specific tagged version:

~~~bash
AI_FACTORY_VERSION=v0.2.0 sh install.sh
~~~

Windows users can download and extract the matching ZIP from GitHub Releases.

## Source checkout launcher

The standalone shell launcher creates a local virtual environment and installs the
project when required:

~~~bash
git clone https://github.com/mastaan66/multi-agent-coding-tool.git
cd multi-agent-coding-tool
./ai-factory.sh --demo "Build a todo API"
~~~

run.sh remains as a compatibility alias.

## Python package

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
ai-factory --help
~~~

## Build your own executable

~~~bash
python -m pip install -e ".[release]"
./scripts/build_binary.sh
~~~

Outputs:

~~~text
dist/ai-factory
dist/release/ai-factory-<platform>-<architecture>.<archive>
dist/release/ai-factory-<platform>-<architecture>.<archive>.sha256
~~~

## Requirements

- Python 3.10 or newer for source installations.
- Linux, macOS, or Windows for release binaries.
- An OpenAI API key for live mode.
- No API key or network access for demo mode.
