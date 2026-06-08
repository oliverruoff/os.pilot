# OSPilot

OSPilot is a macOS/Windows desktop cursor companion for `pi-coding-agent`.

This repository contains a Python/PySide6 desktop shell, a JSON-RPC bridge to `pi`, a local authenticated IPC server for desktop tools, TypeScript pi tool extensions, and a drop-in pi skills folder.

## Structure

```text
src/ospilot/desktop/macos/    macOS desktop implementation
src/ospilot/desktop/windows/  Windows desktop implementation
pi/tools/                     TypeScript pi tool extensions
pi/skills/                    Referenced pi skills drop-in folder
```

## Coding Agent Setup Guide

Use this section as an instruction prompt for a coding agent that should set up
OSPilot on a user's machine.

You are setting up OSPilot, a desktop companion for `pi-coding-agent`. OSPilot
does not install `pi-coding-agent` itself. Before OSPilot can run, the `pi`
executable must be installed and available on `PATH`, or configured explicitly
via OSPilot's `pi.executable` setting.

Complete the setup end-to-end. Do not stop after installing dependencies. Keep
going until OSPilot starts successfully or until you need information only the
user can provide, such as API keys or the desired LLM provider/model.

### Required Software

- Python 3.11 or newer
- Node.js and npm
- `pi-coding-agent`
- LLM provider credentials and model configuration for `pi-coding-agent`

### 1. Check Python

Check whether Python 3.11 or newer is available:

```bash
python3 --version
```

On Windows, also try:

```powershell
py -3 --version
```

If Python is missing or too old, guide the user through installing a supported
version before continuing. Common options:

- macOS: install Python from <https://www.python.org/downloads/> or with Homebrew: `brew install python`
- Windows: install Python from <https://www.python.org/downloads/> or with winget: `winget install Python.Python.3.12`

After installation, rerun the version check and continue only once Python 3.11+
works.

### 2. Check Node.js And npm

`pi-coding-agent` can be installed through npm. Check whether Node.js and npm are
available:

```bash
node --version
npm --version
```

If Node.js or npm is missing, guide the user through installing Node.js before
continuing. Common options:

- macOS: install Node.js from <https://nodejs.org/> or with Homebrew: `brew install node`
- Windows: install Node.js from <https://nodejs.org/> or with winget: `winget install OpenJS.NodeJS.LTS`

After installation, rerun `node --version` and `npm --version`.

### 3. Install pi-coding-agent

First check whether `pi` is already installed:

```bash
pi --help
```

If that works, continue to the next step.

If `pi` is missing, install `pi-coding-agent` with npm. Prefer a global install
because OSPilot expects a `pi` executable on `PATH` by default:

```bash
npm install -g @earendil-works/pi-coding-agent
```

Then verify again:

```bash
pi --help
```

If global npm installation fails because of permissions, do not blindly use
`sudo`. Prefer guiding the user through fixing npm permissions, using a Node
version manager, or choosing another install location. If the user explicitly
approves using administrator privileges, proceed carefully.

If the user wants a local npm install instead, run:

```bash
npm install @earendil-works/pi-coding-agent
```

A local install may not expose `pi` globally. In that case, either fix `PATH`, use
the local executable path in OSPilot config, or ask the user which option they
prefer. OSPilot can be pointed at a custom executable with:

```yaml
pi:
  executable: /absolute/path/to/pi
  args: []
```

### 4. Configure Provider And Model

OSPilot passes provider/model environment through to `pi-coding-agent`. Check
whether the required environment variables are already configured. If they are
missing, ask the user which provider and model they want to use.

Do not invent API keys, account IDs, model names, or provider-specific secrets.
Ask the user for missing values and explain where they can get them.

For local project configuration, create or update a `.env` file in this
repository. Example:

```bash
KIMI_API_KEY=replace-me
PI_ARGS=--model kimi-coding/<model-name>
```

Adjust the variables for the provider the user chooses. If the selected provider
requires a different API key variable, set that provider-specific variable
instead. Keep `PI_ARGS` focused on arguments that should be passed to `pi`, such
as the model selection.

### 5. Install OSPilot Dependencies

Create and activate a Python virtual environment.

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
```

For the simplest manual run path, install the runtime dependencies:

```bash
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
py -m pip install -r requirements.txt
```

Alternatively, install OSPilot from this repository. This also creates the
`ospilot` command:

```bash
pip install -e .
```

If development/test dependencies are needed, use:

```bash
pip install -e '.[dev]'
```

### 6. Optional OSPilot Config

By default, OSPilot runs `pi` from `PATH`. If `pi` is not available on `PATH`, or
if the user wants custom default arguments, create or update the OSPilot config
file.

Default config locations:

- macOS/Linux: `~/.config/ospilot/config.yaml`
- Windows: `%APPDATA%\OSPilot\config.yaml`

Example config:

```yaml
pi:
  executable: pi
  args: []
privacy:
  store_screenshots: false
  store_conversations: false
  redact_secrets_best_effort: true
  debug_mode: false
ui:
  mouse_move_debug_teleport: false
```

Use an absolute path for `pi.executable` if `pi` is installed but not available
on `PATH`.

### 7. Start And Verify OSPilot

Start OSPilot:

macOS/Linux:

```bash
python main.py
```

Windows PowerShell:

```powershell
py main.py
```

If you installed the package with `pip install -e .`, you can also run:

```bash
ospilot
```

Verify all of the following:

- `pi --help` works.
- `ospilot` starts without crashing.
- The `pi` RPC process starts successfully.
- Provider/model configuration is accepted.
- The user can submit a prompt through OSPilot and receives a response.

If setup fails, inspect the terminal output and OSPilot logs, fix the missing
dependency or configuration issue, and retry. Do not claim setup is complete
until OSPilot has started successfully and the user can run at least one prompt.

## Run

Simple manual run:

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py main.py
```

Package install run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
ospilot
```

On Windows, activate the virtualenv with `.venv\Scripts\activate` and run
`py -m pip install -e .` and `ospilot`. Windows support targets Windows 11 and
uses Windows-only dependencies through platform markers.

Set provider/model configuration the same way you would for `pi` directly, for example:

```bash
export PI_ARGS="--model provider/model"
```

## Test

```bash
pip install -e '.[dev]'
pytest
```
