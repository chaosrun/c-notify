#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NO_CODEX=false
NO_CLAUDE=false
NO_PATH=false

HOME_DIR="${C_NOTIFY_INSTALL_HOME:-$HOME}"
BIN_DIR="${C_NOTIFY_BIN_DIR:-$HOME_DIR/.local/bin}"
CODEX_CONFIG_FILE="${C_NOTIFY_CODEX_CONFIG:-$HOME_DIR/.codex/config.toml}"
CLAUDE_SETTINGS_FILE="${C_NOTIFY_CLAUDE_SETTINGS:-$HOME_DIR/.claude/settings.json}"

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --no-codex     Skip writing ~/.codex/config.toml
  --no-claude    Skip writing ~/.claude/settings.json
  --no-path      Skip PATH export block in shell rc file
  --bin-dir=DIR  Install c-notify symlink to DIR
  -h, --help     Show help

Environment overrides:
  C_NOTIFY_INSTALL_HOME
  C_NOTIFY_BIN_DIR
  C_NOTIFY_CODEX_CONFIG
  C_NOTIFY_CLAUDE_SETTINGS
  C_NOTIFY_RC_FILE
  C_NOTIFY_HOME
EOF
}

for arg in "$@"; do
  case "$arg" in
    --no-codex)
      NO_CODEX=true
      ;;
    --no-claude)
      NO_CLAUDE=true
      ;;
    --no-path)
      NO_PATH=true
      ;;
    --bin-dir=*)
      BIN_DIR="${arg#*=}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required." >&2
  exit 1
fi

detect_rc_file() {
  local shell_name
  shell_name="$(basename "${SHELL:-}")"
  case "$shell_name" in
    zsh)
      echo "$HOME_DIR/.zshrc"
      ;;
    bash)
      if [ -f "$HOME_DIR/.bashrc" ]; then
        echo "$HOME_DIR/.bashrc"
      else
        echo "$HOME_DIR/.bash_profile"
      fi
      ;;
    *)
      echo "$HOME_DIR/.profile"
      ;;
  esac
}

RC_FILE="${C_NOTIFY_RC_FILE:-$(detect_rc_file)}"

ensure_path_block() {
  if [ "$NO_PATH" = true ]; then
    return
  fi

  mkdir -p "$(dirname "$RC_FILE")"
  touch "$RC_FILE"

  python3 - <<'PY' "$RC_FILE" "$BIN_DIR"
import sys
from pathlib import Path

rc_path = Path(sys.argv[1])
bin_dir = sys.argv[2]
start = "# >>> c-notify path >>>"
end = "# <<< c-notify path <<<"
line = f'export PATH="{bin_dir}:$PATH"'

text = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
if text and not text.endswith("\n"):
    text += "\n"
lines = text.splitlines()

out = []
inside = False
for ln in lines:
    if ln.strip() == start:
        inside = True
        continue
    if ln.strip() == end:
        inside = False
        continue
    if not inside:
        out.append(ln)

if out and out[-1].strip():
    out.append("")
out.extend([start, line, end])

rc_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

install_bin() {
  mkdir -p "$BIN_DIR"
  chmod +x "$SCRIPT_DIR/c-notify" "$SCRIPT_DIR/c-notify.py"
  ln -sf "$SCRIPT_DIR/c-notify" "$BIN_DIR/c-notify"
}

update_codex_config() {
  mkdir -p "$(dirname "$CODEX_CONFIG_FILE")"
  touch "$CODEX_CONFIG_FILE"

  python3 - <<'PY' "$CODEX_CONFIG_FILE" "$SCRIPT_DIR/c-notify.py"
import json
import re
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
script_path = Path(sys.argv[2])

text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
if text and not text.endswith("\n"):
    text += "\n"
lines = text.splitlines()

notify_line = "notify = " + json.dumps(["python3", str(script_path), "hook", "--tool", "codex"])

def is_table_header(line: str) -> bool:
    return re.match(r"^\s*\[[^\]]+\]\s*$", line) is not None

def set_top_level_key(lines_in, key, value_line):
    out = []
    in_top = True
    found = False
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for line in lines_in:
        if is_table_header(line):
            in_top = False
        if in_top and key_re.match(line):
            if not found:
                out.append(value_line)
                found = True
            continue
        out.append(line)
    if not found:
        insert_at = 0
        while insert_at < len(out):
            stripped = out[insert_at].strip()
            if stripped == "" or stripped.startswith("#"):
                insert_at += 1
                continue
            break
        out.insert(insert_at, value_line)
    return out

new_lines = set_top_level_key(lines, "notify", notify_line)
config_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
PY
}

update_claude_settings() {
  mkdir -p "$(dirname "$CLAUDE_SETTINGS_FILE")"
  [ -f "$CLAUDE_SETTINGS_FILE" ] || echo '{}' > "$CLAUDE_SETTINGS_FILE"

  python3 - <<'PY' "$CLAUDE_SETTINGS_FILE" "$SCRIPT_DIR/c-notify.py"
import json
import sys
from pathlib import Path

settings_path = Path(sys.argv[1])
script_path = Path(sys.argv[2])
cmd = f"python3 {script_path} hook --tool claude"

try:
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        settings = {}
except Exception:
    settings = {}

hooks = settings.setdefault("hooks", {})
if not isinstance(hooks, dict):
    hooks = {}
    settings["hooks"] = hooks

events = [
    ("SessionStart", "", True),
    ("SessionEnd", "", True),
    ("SubagentStart", "", True),
    ("UserPromptSubmit", "", True),
    ("Stop", "", True),
    ("Notification", "", True),
    ("PermissionRequest", "", True),
    ("PostToolUseFailure", "Bash", True),
    ("PreCompact", "", True),
]

def make_hook(async_mode: bool):
    hook = {
        "type": "command",
        "command": cmd,
        "timeout": 10,
    }
    if async_mode:
        hook["async"] = True
    return hook

def is_c_notify_command(command: str) -> bool:
    normalized = " ".join(str(command).lower().split())
    return "c-notify" in normalized and "hook --tool claude" in normalized

def is_c_notify_entry(entry):
    if not isinstance(entry, dict):
        return False
    direct_command = entry.get("command")
    if isinstance(direct_command, str) and is_c_notify_command(direct_command):
        return True
    subhooks = entry.get("hooks", [])
    if not isinstance(subhooks, list):
        return False
    for h in subhooks:
        if not isinstance(h, dict):
            continue
        if is_c_notify_command(str(h.get("command", ""))):
            return True
    return False

managed_events = {name for name, _, _ in events}

# Remove stale c-notify entries globally so dropped events (for example SubagentStop)
# no longer keep spawning no-op hook processes.
for event_name in list(hooks.keys()):
    event_hooks = hooks.get(event_name, [])
    if not isinstance(event_hooks, list):
        continue
    cleaned = [e for e in event_hooks if not is_c_notify_entry(e)]
    if event_name in managed_events:
        hooks[event_name] = cleaned
    elif cleaned:
        hooks[event_name] = cleaned
    else:
        del hooks[event_name]

for event_name, matcher, async_mode in events:
    event_hooks = hooks.get(event_name, [])
    if not isinstance(event_hooks, list):
        event_hooks = []
    event_hooks.append(
        {
            "matcher": matcher,
            "hooks": [make_hook(async_mode)],
        }
    )
    hooks[event_name] = event_hooks

settings["hooks"] = hooks
settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
PY
}

echo "Installing c-notify..."
install_bin
ensure_path_block

if [ "$NO_CODEX" = false ]; then
  update_codex_config
fi
if [ "$NO_CLAUDE" = false ]; then
  update_claude_settings
fi

# Initialize sound folder structure and event README files.
"$SCRIPT_DIR/c-notify" init >/dev/null 2>&1 || true

echo ""
echo "Install complete."
echo "Binary: $BIN_DIR/c-notify"
echo "Shell rc: $RC_FILE"
[ "$NO_CODEX" = false ] && echo "Codex config updated: $CODEX_CONFIG_FILE"
[ "$NO_CLAUDE" = false ] && echo "Claude settings updated: $CLAUDE_SETTINGS_FILE"
echo ""
echo "Next:"
echo "  source \"$RC_FILE\""
echo "  c-notify status"
echo "  c-notify events"
