# c-notify

`c-notify` is a lightweight local hook sound router for **Codex** and **Claude Code**.
It plays a random audio file from `~/.c-notify/sounds/<tool>/<event>/` when hook events arrive.

Audio files are user-provided. The repository does not bundle sound assets.

<p align="center">
  <a href="README_ZH.md">📖 简体中文说明</a>&nbsp;&nbsp;|&nbsp;&nbsp;<a href="docs/VS_CODE_REMOTE_SSH.md">🔗 Remote SSH Guide</a>
</p>

## Features

- Tool-specific event namespaces (`codex` and `claude`) with independent event sets
- Random playback from per-event folders
- Global portable switch: `on / off / toggle / status`
- Linux/macOS playback backend support
- Event folder bootstrap with bilingual `README.md` per folder
- Codex hook support for `SessionStart`, `UserPromptSubmit`, `PermissionRequest`, and `PreCompact`
- Optional remote relay mode for VS Code Remote SSH and other SSH-based remote workflows
- Deterministic Codex routing: `agent-turn-complete` maps directly to `task-complete`

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
- Writes/updates Codex hooks in `~/.codex/hooks.json`
- Writes/updates Claude hooks in `~/.claude/settings.json`

Useful flags:

```bash
./install.sh --no-codex
./install.sh --no-claude
./install.sh --no-path
./install.sh --bin-dir=/custom/bin
./install.sh --remote-endpoint=http://127.0.0.1:38765
./install.sh --remote-endpoint=http://127.0.0.1:38765 --remote-token=secret-token
```

## Sound Directories

Codex:

- `~/.c-notify/sounds/codex/task-acknowledge/` (from Codex `UserPromptSubmit`)
- `~/.c-notify/sounds/codex/task-complete/`
- `~/.c-notify/sounds/codex/permission-needed/` (from Codex `PermissionRequest`)
- `~/.c-notify/sounds/codex/task-error/`
- `~/.c-notify/sounds/codex/context-compact/` (from Codex `PreCompact`)
- `~/.c-notify/sounds/codex/resource-limit/`
- `~/.c-notify/sounds/codex/session-start/` (from Codex `SessionStart`)

Claude:

- `~/.c-notify/sounds/claude/session-start/`
- `~/.c-notify/sounds/claude/session-end/` (optional)
- `~/.c-notify/sounds/claude/subagent-start/` (optional)
- `~/.c-notify/sounds/claude/task-acknowledge/`
- `~/.c-notify/sounds/claude/task-complete/`
- `~/.c-notify/sounds/claude/permission-needed/`
- `~/.c-notify/sounds/claude/context-compact/`
- `~/.c-notify/sounds/claude/resource-limit/`

## Hook Wiring

### Codex (`~/.codex/config.toml` and `~/.codex/hooks.json`)

`config.toml` keeps `notify` for completion and enables the hooks engine:

```toml
notify = ["python3", "/ABSOLUTE/PATH/TO/c-notify/c-notify.py", "hook", "--tool", "codex"]

[features]
hooks = true
```

`hooks.json` wires `SessionStart`, `UserPromptSubmit`, `PermissionRequest`, and `PreCompact` into `c-notify`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool codex",
            "timeout": 10,
            "statusMessage": "Playing c-notify session-start sound"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool codex",
            "timeout": 10,
            "statusMessage": "Playing c-notify task-acknowledge sound"
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool codex",
            "timeout": 10,
            "statusMessage": "Playing c-notify permission-needed sound"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool codex",
            "timeout": 10,
            "statusMessage": "Playing c-notify context-compact sound"
          }
        ]
      }
    ]
  }
}
```

Notes:

- Codex `notify` currently sends `agent-turn-complete` payloads in normal operation.
- Codex does not use message-semantic inference; `agent-turn-complete` always routes to `task-complete`.
- Codex hooks are currently used for `SessionStart`, `UserPromptSubmit`, `PermissionRequest`, and `PreCompact`.
- New or changed Codex hooks may require review in the TUI; open `/hooks` and approve the `c-notify` entries when Codex prompts for review.
- `UserPromptSubmit` maps to `task-acknowledge`.
- `PermissionRequest` maps to `permission-needed`.
- `PreCompact` maps to `context-compact`; `PostCompact` is recognized as the same category but is not installed by default to avoid double playback.
- The first `UserPromptSubmit` immediately following `SessionStart` for the same Codex `session_id` is suppressed to avoid double playback on a brand-new or resumed session.
- `Stop` is intentionally not registered in `hooks.json`; completion already comes from `notify`, so wiring both would duplicate playback.
- `PreToolUse` and `PostToolUse` are intentionally not registered by default because they are high-frequency tool events.
- Codex `task-error` and `resource-limit` remain explicit/manual categories unless Codex emits native events for them later.
- Example files are included in [`examples/codex-config.toml`](examples/codex-config.toml) and [`examples/codex-hooks.json`](examples/codex-hooks.json).

### Claude Code (`~/.claude/settings.json`)

Every event uses the same command; only the event key and `matcher` differ:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /ABSOLUTE/PATH/TO/c-notify/c-notify.py hook --tool claude",
            "timeout": 10,
            "async": true
          }
        ]
      }
    ]
  }
}
```

Repeat the same structure for each event:

| Event | `matcher` |
|-------|-----------|
| `SessionStart` | `""` |
| `SessionEnd` | `""` |
| `SubagentStart` | `""` |
| `UserPromptSubmit` | `""` |
| `Stop` | `""` |
| `PermissionRequest` | `""` |
| `PreCompact` | `""` |

`Notification` is intentionally not registered; `PermissionRequest` is the only permission trigger.

## Remote SSH

Remote mode is optional. If you do nothing, `c-notify` keeps working exactly as a local-only tool.

Use remote mode when Codex or Claude runs on a remote machine but you want the sound to play on your local machine.

1. On your local machine, start the receiver:

```bash
c-notify serve --listen 127.0.0.1 --port 38765
```

2. Add an SSH reverse tunnel on your local machine for that remote host:

```sshconfig
Host my-remote
    HostName your.remote.host
    User your_user
    RemoteForward 127.0.0.1:38765 127.0.0.1:38765
```

3. On the remote machine, install relay-based hooks instead of local playback hooks:

```bash
./install.sh --remote-endpoint=http://127.0.0.1:38765
```

4. Optional: protect the receiver with a token on both sides:

```bash
# local machine
c-notify serve --listen 127.0.0.1 --port 38765 --token secret-token

# remote machine
./install.sh --remote-endpoint=http://127.0.0.1:38765 --remote-token=secret-token
```

Notes:

- `install.sh` only switches to relay mode when you explicitly pass `--remote-endpoint`.
- Local installs remain direct-playback installs.
- The receiver exposes `GET /healthz` and accepts `POST /hook/codex` and `POST /hook/claude`.
- Full setup guide: [`docs/VS_CODE_REMOTE_SSH.md`](docs/VS_CODE_REMOTE_SSH.md)

Related files:

| | Hook examples | Autostart (systemd) | Autostart (launchd) |
|---|---|---|---|
| Codex | [`codex-config-remote.toml`](examples/codex-config-remote.toml), [`codex-hooks-remote.json`](examples/codex-hooks-remote.json) | [`c-notify-serve.service`](examples/systemd/c-notify-serve.service) | [`com.c-notify.serve.plist`](examples/launchd/com.c-notify.serve.plist) |
| Claude | [`claude-hooks-remote.json`](examples/claude-hooks-remote.json) | [`c-notify-tunnel.service`](examples/systemd/c-notify-tunnel.service) | [`com.c-notify.tunnel.plist`](examples/launchd/com.c-notify.tunnel.plist) |

## Commands

Setup:

```bash
./install.sh
./c-notify init
./c-notify init --refresh-readmes
```

Control:

```bash
./c-notify on
./c-notify off
./c-notify toggle
./c-notify status
./c-notify events
./c-notify events --tool codex
./c-notify events --tool claude
```

Manual playback:

```bash
./c-notify play --tool claude --event task-complete
./c-notify play --tool codex --event task-acknowledge
```

Debug:

```bash
./c-notify hook --tool codex --event session-start --debug
./c-notify hook --tool codex --debug
./c-notify hook --tool claude --debug
tail -n 40 ~/.c-notify/logs/hook-events.jsonl
```

Remote:

```bash
./c-notify serve --listen 127.0.0.1 --port 38765
./c-notify relay --tool codex --endpoint http://127.0.0.1:38765 --debug
```

## Config

Runtime config path:

- `~/.c-notify/config.json`
- `~/.c-notify/state.json`
- `~/.c-notify/logs/hook-events.jsonl`

Optional override:

- `C_NOTIFY_HOME=/custom/path` to relocate config/state/sounds root.
- `C_NOTIFY_INSTALL_HOME=/custom/home` to relocate install targets used by `install.sh`.
- `C_NOTIFY_REMOTE_ENDPOINT=http://127.0.0.1:38765` to default `relay` and remote install wiring to one receiver.
- `C_NOTIFY_REMOTE_TOKEN=secret-token` to reuse the same token for `serve`, `relay`, and remote install wiring.

Important keys:

- `enabled`: master on/off switch
- `sound_root`: default `~/.c-notify/sounds`
- `volume`: playback volume (backend dependent)
- `extensions`: allowed audio extensions
- `prevent_overlap`: skip new playback while prior process is alive
- `cooldown_seconds` and `cooldown_by_event`: optional throttling
- `hook_strict_exit`: default `false`; when `true`, hook exits non-zero for unmapped/no-sound outcomes

Hook debug log:

- `~/.c-notify/logs/hook-events.jsonl` records recent hook invocations for Codex and Claude
- payload text is truncated to keep entries small
- rotation is automatic: `256 KiB x 4 files`

## Platform Support

- macOS: `afplay`
- Linux: `pw-play`, `paplay`, `ffplay`, `aplay` (fallback order)

Windows support is intentionally out of scope for this first version.
