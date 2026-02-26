# c-notify

`c-notify` is a lightweight local hook sound router for **Codex** and **Claude Code**.
It plays a random audio file from `~/.c-notify/sounds/<tool>/<event>/` when hook events arrive.

Audio files are user-provided. The repository does not bundle sound assets.

## Features

- Tool-specific event namespaces (`codex` and `claude`) with independent event sets
- Random playback from per-event folders
- Global portable switch: `on / off / toggle / status`
- Linux/macOS playback backend support
- Event folder bootstrap with bilingual `README.md` per folder
- Codex inferred event routing from `agent-turn-complete` message text

## Quick Start

```bash
cd c-notify
chmod +x c-notify c-notify.py
./c-notify init
./c-notify status
./c-notify events
```

## One-Command Install

```bash
cd c-notify
chmod +x install.sh
./install.sh
```

What `install.sh` does:

- Installs `c-notify` to `~/.local/bin/c-notify` (symlink)
- Appends a PATH block to your shell rc file (`~/.zshrc` for zsh, `~/.bashrc`/`~/.bash_profile` for bash)
- Writes/updates Codex notify config in `~/.codex/config.toml`
- Writes/updates Claude hooks in `~/.claude/settings.json`

Useful flags:

```bash
./install.sh --no-codex
./install.sh --no-claude
./install.sh --no-path
./install.sh --bin-dir=/custom/bin
```

Then put your own files in folders like:

- `~/.c-notify/sounds/codex/task-complete/`
- `~/.c-notify/sounds/codex/permission-needed/`
- `~/.c-notify/sounds/claude/stop/`
- `~/.c-notify/sounds/claude/permission-request/`

## Hook Wiring

### Codex (`~/.codex/config.toml`)

```toml
notify = ["python3", "/ABSOLUTE/PATH/TO/c-notify/c-notify.py", "hook", "--tool", "codex"]
```

Notes:

- Codex primarily sends `agent-turn-complete` through `notify`.
- If you also configure TUI notifications, `approval-requested` can be used by your hook pipeline.

### Claude Code (`~/.claude/settings.json`)

Use one command entry for all events:

```json
{
  "hooks": {
    "SessionStart": [
      { "matcher": "", "hooks": [ { "type": "command", "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool claude", "timeout": 10, "async": true } ] }
    ],
    "SessionEnd": [
      { "matcher": "", "hooks": [ { "type": "command", "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool claude", "timeout": 10, "async": true } ] }
    ],
    "SubagentStart": [
      { "matcher": "", "hooks": [ { "type": "command", "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool claude", "timeout": 10, "async": true } ] }
    ],
    "UserPromptSubmit": [
      { "matcher": "", "hooks": [ { "type": "command", "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool claude", "timeout": 10, "async": true } ] }
    ],
    "Stop": [
      { "matcher": "", "hooks": [ { "type": "command", "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool claude", "timeout": 10, "async": true } ] }
    ],
    "Notification": [
      { "matcher": "", "hooks": [ { "type": "command", "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool claude", "timeout": 10, "async": true } ] }
    ],
    "PermissionRequest": [
      { "matcher": "", "hooks": [ { "type": "command", "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool claude", "timeout": 10, "async": true } ] }
    ],
    "PostToolUseFailure": [
      { "matcher": "Bash", "hooks": [ { "type": "command", "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool claude", "timeout": 10, "async": true } ] }
    ],
    "PreCompact": [
      { "matcher": "", "hooks": [ { "type": "command", "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool claude", "timeout": 10, "async": true } ] }
    ]
  }
}
```

## Event Coverage

List current known events:

```bash
./c-notify events
./c-notify events --tool codex
./c-notify events --tool claude
```

The script also supports unknown/custom event folder names by slug.

## Commands

```bash
./install.sh
./c-notify init
./c-notify init --refresh-readmes
./c-notify on
./c-notify off
./c-notify toggle
./c-notify status
./c-notify events --tool claude
./c-notify play --tool claude --event stop
./c-notify hook --tool codex --debug
./c-notify hook --tool claude --debug
```

## Config

Runtime config path:

- `~/.c-notify/config.json`

Optional override:

- `C_NOTIFY_HOME=/custom/path` to relocate config/state/sounds root.
- `C_NOTIFY_INSTALL_HOME=/custom/home` to relocate install targets used by `install.sh`.

Important keys:

- `enabled`: master on/off switch
- `sound_root`: default `~/.c-notify/sounds`
- `volume`: playback volume (backend dependent)
- `extensions`: allowed audio extensions
- `prevent_overlap`: skip new playback while prior process is alive
- `cooldown_seconds` and `cooldown_by_event`: optional throttling
- `codex_keywords`: keyword inference for `permission-needed`, `task-error`, `resource-limit`

## Platform Support

- macOS: `afplay`
- Linux: `pw-play`, `paplay`, `ffplay`, `aplay` (fallback order)

Windows support is intentionally out of scope for this first version.
