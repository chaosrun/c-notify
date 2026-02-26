#!/usr/bin/env python3
"""c-notify: event-based sound notifications for Codex and Claude."""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl  # Unix only (macOS/Linux)
except ImportError:  # pragma: no cover
    fcntl = None

HOME_DIR = Path.home()
APP_DIR = Path(os.environ.get("C_NOTIFY_HOME", str(HOME_DIR / ".c-notify"))).expanduser()
CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "state.json"
LOCK_PATH = APP_DIR / ".state.lock"
DEFAULT_SOUND_ROOT = APP_DIR / "sounds"

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "volume": 1.0,
    "sound_root": str(DEFAULT_SOUND_ROOT),
    "extensions": [".wav", ".mp3", ".ogg", ".m4a", ".aac", ".aiff", ".flac"],
    "prevent_overlap": False,
    "cooldown_seconds": 0.0,
    "cooldown_by_event": {},
    "codex_keywords": {
        "permission-needed": [
            "needs your approval",
            "need your approval",
            "approval requested",
            "approve this",
            "approve the command",
            "allow this command",
            "permission prompt",
        ],
        "task-error": [
            "error",
            "failed",
            "unable",
            "cannot",
            "can't",
            "denied",
            "permission denied",
            "not found",
            "timed out",
            "exception",
        ],
        "resource-limit": [
            "rate limit",
            "quota",
            "429",
            "token limit",
            "context length",
            "context window",
        ],
    },
}

DEFAULT_STATE: dict[str, Any] = {
    "last_played": {},
    "last_event_ts": {},
    "playback_pid": None,
}

EVENT_DOCS: dict[str, dict[str, dict[str, str]]] = {
    "codex": {
        "agent-turn-complete": {
            "en": "Raw Codex notify event after an assistant turn completes.",
            "zh": "Codex 助手回合完成后触发的原始 notify 事件。",
        },
        "task-complete": {
            "en": "Inferred completion event from agent-turn-complete when no error/permission/resource hint is detected.",
            "zh": "从 agent-turn-complete 推断出的普通完成事件（未命中错误/权限/资源关键词）。",
        },
        "permission-needed": {
            "en": "Inferred permission-required event, or mapped from approval-style events.",
            "zh": "推断出的需要权限事件，或由审批类事件映射而来。",
        },
        "task-error": {
            "en": "Inferred error event from turn result text, or mapped from fail/error style events.",
            "zh": "从回合文本推断出的错误事件，或由 fail/error 类事件映射而来。",
        },
        "resource-limit": {
            "en": "Inferred resource-limit event from turn result text (for example quota/rate-limit).",
            "zh": "从回合文本推断出的资源限制事件（如 quota/rate-limit）。",
        },
        "approval-requested": {
            "en": "Codex TUI approval-requested event when configured in notifications.",
            "zh": "在 Codex TUI notifications 配置中可触发的 approval-requested 事件。",
        },
        "session-start": {
            "en": "Optional session start event used by adapters or custom wiring.",
            "zh": "可选的会话开始事件，通常由适配层或自定义脚本触发。",
        },
    },
    "claude": {
        "session-start": {
            "en": "Claude SessionStart event (generic fallback for session start).",
            "zh": "Claude 的 SessionStart 事件（会话开始通用回退目录）。",
        },
        "session-start-startup": {
            "en": "SessionStart variant when source is startup.",
            "zh": "SessionStart 的 startup 变体。",
        },
        "session-start-clear": {
            "en": "SessionStart variant when source is clear.",
            "zh": "SessionStart 的 clear 变体。",
        },
        "session-start-resume": {
            "en": "SessionStart variant when source is resume.",
            "zh": "SessionStart 的 resume 变体。",
        },
        "session-start-compact": {
            "en": "SessionStart variant when source is compact.",
            "zh": "SessionStart 的 compact 变体。",
        },
        "session-end": {
            "en": "Claude SessionEnd event.",
            "zh": "Claude 的 SessionEnd 事件。",
        },
        "subagent-start": {
            "en": "Claude SubagentStart event.",
            "zh": "Claude 的 SubagentStart 事件。",
        },
        "subagent-stop": {
            "en": "Sub-agent completion event (adapter or tool dependent).",
            "zh": "子代理完成事件（取决于适配器或具体工具）。",
        },
        "user-prompt-submit": {
            "en": "Claude UserPromptSubmit event.",
            "zh": "Claude 的 UserPromptSubmit 事件。",
        },
        "stop": {
            "en": "Claude Stop event (task completed and waiting for next user input).",
            "zh": "Claude 的 Stop 事件（任务完成并等待用户下一步输入）。",
        },
        "notification": {
            "en": "Claude Notification event (generic fallback).",
            "zh": "Claude 的 Notification 事件（通用回退目录）。",
        },
        "notification-permission-prompt": {
            "en": "Notification subtype: permission_prompt.",
            "zh": "Notification 子类型：permission_prompt。",
        },
        "notification-idle-prompt": {
            "en": "Notification subtype: idle_prompt.",
            "zh": "Notification 子类型：idle_prompt。",
        },
        "notification-elicitation-dialog": {
            "en": "Notification subtype: elicitation_dialog.",
            "zh": "Notification 子类型：elicitation_dialog。",
        },
        "permission-request": {
            "en": "Claude PermissionRequest event.",
            "zh": "Claude 的 PermissionRequest 事件。",
        },
        "post-tool-use-failure": {
            "en": "Claude PostToolUseFailure event (often used for failed Bash/tool execution).",
            "zh": "Claude 的 PostToolUseFailure 事件（常用于 Bash/工具执行失败）。",
        },
        "pre-compact": {
            "en": "Claude PreCompact event before context compaction starts.",
            "zh": "Claude 在上下文压缩前触发的 PreCompact 事件。",
        },
        "pre-tool-use": {
            "en": "Tool pre-execution event (tooling/version dependent).",
            "zh": "工具执行前事件（取决于工具与版本）。",
        },
        "post-tool-use": {
            "en": "Tool post-execution event (tooling/version dependent).",
            "zh": "工具执行后事件（取决于工具与版本）。",
        },
    },
}

CODEX_ALIAS_MAP = {
    "agent-turn-complete": "agent-turn-complete",
    "complete": "task-complete",
    "done": "task-complete",
    "task-complete": "task-complete",
    "approval-requested": "approval-requested",
    "permission": "permission-needed",
    "permission-needed": "permission-needed",
    "approve": "permission-needed",
    "approval": "permission-needed",
    "error": "task-error",
    "task-error": "task-error",
    "fail": "task-error",
    "failed": "task-error",
    "resource-limit": "resource-limit",
    "rate-limit": "resource-limit",
    "quota": "resource-limit",
    "session-start": "session-start",
    "start": "session-start",
}

CLAUDE_ALIAS_MAP = {
    "sessionstart": "session-start",
    "session-start": "session-start",
    "sessionend": "session-end",
    "session-end": "session-end",
    "subagentstart": "subagent-start",
    "subagent-start": "subagent-start",
    "subagentstop": "subagent-stop",
    "subagent-stop": "subagent-stop",
    "userpromptsubmit": "user-prompt-submit",
    "user-prompt-submit": "user-prompt-submit",
    "stop": "stop",
    "notification": "notification",
    "permissionrequest": "permission-request",
    "permission-request": "permission-request",
    "posttoolusefailure": "post-tool-use-failure",
    "post-tool-use-failure": "post-tool-use-failure",
    "precompact": "pre-compact",
    "pre-compact": "pre-compact",
    "pretooluse": "pre-tool-use",
    "pre-tool-use": "pre-tool-use",
    "posttooluse": "post-tool-use",
    "post-tool-use": "post-tool-use",
}


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return json.loads(json.dumps(default))


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def _merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for key, value in src.items():
        if isinstance(dst.get(key), dict) and isinstance(value, dict):
            _merge(dst[key], value)
        else:
            dst[key] = value
    return dst


def load_config() -> dict[str, Any]:
    config = _merge(json.loads(json.dumps(DEFAULT_CONFIG)), _load_json(CONFIG_PATH, {}))
    _save_json(CONFIG_PATH, config)
    return config


def load_state() -> dict[str, Any]:
    return _merge(json.loads(json.dumps(DEFAULT_STATE)), _load_json(STATE_PATH, {}))


def save_state(state: dict[str, Any]) -> None:
    _save_json(STATE_PATH, state)


@contextmanager
def state_lock() -> Any:
    if fcntl is None:
        yield
        return

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _sound_root(config: dict[str, Any]) -> Path:
    raw = str(config.get("sound_root", DEFAULT_SOUND_ROOT))
    return Path(os.path.expandvars(raw)).expanduser()


def _normalize_extensions(config: dict[str, Any]) -> set[str]:
    raw = config.get("extensions", [])
    if not isinstance(raw, list):
        return set(DEFAULT_CONFIG["extensions"])
    normalized = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        ext = item.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.add(ext)
    return normalized or set(DEFAULT_CONFIG["extensions"])


def _is_pid_running(raw_pid: Any) -> bool:
    try:
        pid = int(raw_pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _clamp_float(value: Any, default: float, minimum: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


def _event_cooldown_seconds(config: dict[str, Any], event_name: str) -> float:
    cooldown_by_event = config.get("cooldown_by_event", {})
    if isinstance(cooldown_by_event, dict):
        raw = cooldown_by_event.get(event_name, config.get("cooldown_seconds", 0.0))
    else:
        raw = config.get("cooldown_seconds", 0.0)
    return _clamp_float(raw, default=0.0, minimum=0.0)


def _on_cooldown(config: dict[str, Any], state: dict[str, Any], event_name: str, now_ts: float) -> bool:
    seconds = _event_cooldown_seconds(config, event_name)
    if seconds <= 0:
        return False
    last_event_ts = state.get("last_event_ts", {})
    if not isinstance(last_event_ts, dict):
        return False
    try:
        last_ts = float(last_event_ts.get(event_name, 0.0))
    except (TypeError, ValueError):
        last_ts = 0.0
    if last_ts <= 0:
        return False
    return (now_ts - last_ts) < seconds


def _detect_platform() -> str:
    if sys.platform == "darwin":
        return "mac"
    if sys.platform.startswith("linux"):
        rel = platform.release().lower()
        if "microsoft" in rel or "wsl" in rel:
            return "wsl"
        return "linux"
    return "unknown"


def _play_mac(sound_file: Path, volume: float) -> int | None:
    if not shutil.which("afplay"):
        return None
    proc = subprocess.Popen(
        ["afplay", "-v", str(volume), str(sound_file)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.pid


def _play_linux(sound_file: Path, volume: float) -> int | None:
    volume = _clamp_float(volume, default=1.0, minimum=0.0)
    if shutil.which("pw-play"):
        proc = subprocess.Popen(
            ["pw-play", "--volume", str(min(volume, 4.0)), str(sound_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc.pid
    if shutil.which("paplay"):
        paplay_volume = int(max(0.0, min(volume, 4.0)) * 65536)
        proc = subprocess.Popen(
            ["paplay", "--volume", str(paplay_volume), str(sound_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc.pid
    if shutil.which("ffplay"):
        ffplay_volume = int(max(0.0, min(volume, 4.0)) * 100)
        proc = subprocess.Popen(
            [
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-loglevel",
                "quiet",
                "-volume",
                str(ffplay_volume),
                str(sound_file),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc.pid
    if shutil.which("aplay"):
        proc = subprocess.Popen(
            ["aplay", str(sound_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc.pid
    return None


def play_sound(sound_file: Path, volume: float) -> int | None:
    platform_name = _detect_platform()
    if platform_name == "mac":
        pid = _play_mac(sound_file, volume)
    else:
        pid = _play_linux(sound_file, volume)

    if pid is None:
        print("\a", end="", flush=True)
    return pid


def _list_audio_files(sound_dir: Path, extensions: set[str]) -> list[Path]:
    if not sound_dir.is_dir():
        return []
    files = [
        p
        for p in sound_dir.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    ]
    return sorted(files)


def _pick_sound(state: dict[str, Any], state_key: str, files: list[Path]) -> Path:
    last_played = state.setdefault("last_played", {})
    if not isinstance(last_played, dict):
        last_played = {}
        state["last_played"] = last_played

    last_file = str(last_played.get(state_key, ""))
    candidates = files if len(files) <= 1 else [f for f in files if str(f) != last_file]
    if not candidates:
        candidates = files
    chosen = random.choice(candidates)
    last_played[state_key] = str(chosen)
    return chosen


def _dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        out.append(item)
        seen.add(item)
    return out


def _event_readme_content(tool: str, event_name: str, en: str, zh: str) -> str:
    return (
        f"# {tool}/{event_name}\n\n"
        f"EN: {en}\n\n"
        f"中文: {zh}\n\n"
        "Put your own audio files in this folder. Supported file types are configured in `~/.c-notify/config.json`.\n"
        "请将你自己的音频文件放在这个目录中。支持的文件类型可在 `~/.c-notify/config.json` 中配置。\n"
    )


def init_sound_tree(config: dict[str, Any], refresh_readmes: bool = False) -> None:
    root = _sound_root(config)
    root.mkdir(parents=True, exist_ok=True)

    root_readme = root / "README.md"
    if refresh_readmes or not root_readme.exists():
        root_readme.write_text(
            "# c-notify sound root\n\n"
            "EN: Place tool-specific sounds under `codex/` and `claude/`.\n"
            "Each event folder contains a bilingual README describing trigger timing.\n\n"
            "中文：将音频分别放在 `codex/` 与 `claude/` 下。\n"
            "每个事件目录都带有中英 README，说明该事件的触发时机。\n",
            encoding="utf-8",
        )

    for tool, event_docs in EVENT_DOCS.items():
        for event_name, doc in event_docs.items():
            event_dir = root / tool / event_name
            event_dir.mkdir(parents=True, exist_ok=True)
            readme_path = event_dir / "README.md"
            if refresh_readmes or not readme_path.exists():
                readme_path.write_text(
                    _event_readme_content(
                        tool=tool,
                        event_name=event_name,
                        en=doc["en"],
                        zh=doc["zh"],
                    ),
                    encoding="utf-8",
                )


def _parse_payload(raw_payload: str) -> Any:
    raw_payload = raw_payload.strip()
    if not raw_payload:
        return {}
    try:
        return json.loads(raw_payload)
    except json.JSONDecodeError:
        return {"event": raw_payload}


def _resolve_payload_text(payload_arg: str | None, extra_tokens: list[str]) -> str:
    if payload_arg:
        return payload_arg
    if extra_tokens:
        return extra_tokens[0]
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def _normalize_codex_event(raw_event: str) -> str:
    if not raw_event:
        return ""
    lowered = _slug(raw_event)
    return CODEX_ALIAS_MAP.get(lowered, lowered)


def _infer_codex_event_from_message(message: str, config: dict[str, Any]) -> str:
    lowered = (message or "").lower()
    keywords = config.get("codex_keywords", {})
    if not isinstance(keywords, dict):
        return "task-complete"

    for key in ("permission-needed", "resource-limit", "task-error"):
        terms = keywords.get(key, [])
        if not isinstance(terms, list):
            continue
        for term in terms:
            if isinstance(term, str) and term and term.lower() in lowered:
                return key
    return "task-complete"


def resolve_codex_events(raw_payload_text: str, event_override: str, config: dict[str, Any]) -> tuple[str, list[str]]:
    payload = _parse_payload(raw_payload_text)
    payload_event = ""
    message = ""

    if isinstance(payload, dict):
        payload_event = str(payload.get("type") or payload.get("event") or "")
        message = str(payload.get("last-assistant-message") or payload.get("message") or "")

    raw_event = event_override or payload_event
    normalized = _normalize_codex_event(raw_event)
    payload_is_turn_complete = isinstance(payload, dict) and payload.get("type") == "agent-turn-complete"
    candidates: list[str] = []

    if normalized == "agent-turn-complete":
        inferred = _infer_codex_event_from_message(message, config)
        candidates.extend([inferred, "agent-turn-complete", "task-complete"])
    elif normalized == "approval-requested":
        candidates.extend(["approval-requested", "permission-needed"])
    elif normalized:
        candidates.append(normalized)
        if normalized == "permission-needed":
            candidates.append("approval-requested")
    else:
        candidates.extend(["task-complete", "agent-turn-complete"])

    if payload_is_turn_complete and normalized != "agent-turn-complete":
        inferred = _infer_codex_event_from_message(message, config)
        candidates.insert(0, inferred)

    candidates = _dedupe_keep_order(candidates)
    return normalized or "unknown", candidates


def _normalize_claude_event(raw_event: str) -> str:
    if not raw_event:
        return ""
    key = re.sub(r"[^A-Za-z0-9-]+", "", raw_event).lower()
    return CLAUDE_ALIAS_MAP.get(key, _slug(raw_event))


def resolve_claude_events(raw_payload_text: str, event_override: str) -> tuple[str, list[str]]:
    payload = _parse_payload(raw_payload_text)
    payload_event = ""
    notification_type = ""
    source = ""

    if isinstance(payload, dict):
        payload_event = str(payload.get("hook_event_name") or payload.get("event") or "")
        notification_type = str(payload.get("notification_type") or "")
        source = str(payload.get("source") or "")

    raw_event = event_override or payload_event
    normalized = _normalize_claude_event(raw_event)
    candidates: list[str] = []

    if normalized == "session-start":
        source_slug = _slug(source)
        if source_slug:
            candidates.append(f"session-start-{source_slug}")
        candidates.append("session-start")
    elif normalized == "notification":
        notif_slug = _slug(notification_type)
        if notif_slug:
            candidates.append(f"notification-{notif_slug}")
            if notif_slug == "permission-prompt":
                candidates.append("permission-request")
        candidates.append("notification")
    elif normalized:
        candidates.append(normalized)
    else:
        candidates.append("stop")

    if raw_event:
        raw_slug = _slug(raw_event)
        if raw_slug and raw_slug != normalized and raw_slug not in CLAUDE_ALIAS_MAP:
            candidates.append(raw_slug)

    candidates = _dedupe_keep_order(candidates)
    return normalized or "unknown", candidates


def try_play_event(
    tool: str,
    candidates: list[str],
    config: dict[str, Any],
    state: dict[str, Any],
) -> tuple[Path | None, str | None]:
    sound_root = _sound_root(config)
    extensions = _normalize_extensions(config)
    now_ts = time.time()

    if bool(config.get("prevent_overlap", False)):
        if _is_pid_running(state.get("playback_pid")):
            return None, None
        state["playback_pid"] = None

    for event_name in candidates:
        if _on_cooldown(config, state, event_name, now_ts):
            continue

        event_dir = sound_root / tool / event_name
        files = _list_audio_files(event_dir, extensions)
        if not files:
            continue

        state_key = f"{tool}:{event_name}"
        chosen = _pick_sound(state, state_key, files)
        volume = _clamp_float(config.get("volume", 1.0), default=1.0, minimum=0.0)
        pid = play_sound(chosen, volume)

        last_event_ts = state.setdefault("last_event_ts", {})
        if not isinstance(last_event_ts, dict):
            last_event_ts = {}
            state["last_event_ts"] = last_event_ts
        last_event_ts[event_name] = now_ts

        state["playback_pid"] = pid
        return chosen, event_name

    return None, None


def set_enabled(value: bool) -> int:
    config = load_config()
    config["enabled"] = value
    _save_json(CONFIG_PATH, config)
    print("c-notify: ON" if value else "c-notify: OFF")
    return 0


def cmd_toggle() -> int:
    config = load_config()
    current = bool(config.get("enabled", True))
    return set_enabled(not current)


def cmd_status() -> int:
    config = load_config()
    enabled = bool(config.get("enabled", True))
    print(f"c-notify: {'ON' if enabled else 'OFF'}")
    print(f"config: {CONFIG_PATH}")
    print(f"state: {STATE_PATH}")
    print(f"sound_root: {_sound_root(config)}")
    print("platform_support: macOS/Linux")
    return 0


def cmd_events(tool: str | None) -> int:
    tools = [tool] if tool else ["codex", "claude"]
    for idx, item in enumerate(tools):
        if idx > 0:
            print()
        print(f"[{item}]")
        docs = EVENT_DOCS.get(item, {})
        for event_name, desc in sorted(docs.items()):
            print(f"- {event_name}: {desc['en']}")
    return 0


def cmd_init(refresh_readmes: bool) -> int:
    config = load_config()
    init_sound_tree(config, refresh_readmes=refresh_readmes)
    print(f"c-notify: initialized at {_sound_root(config)}")
    return 0


def cmd_play(tool: str, event_name: str) -> int:
    config = load_config()
    with state_lock():
        state = load_state()
        path, used_event = try_play_event(tool, [event_name], config, state)
        save_state(state)
    if path is None:
        print(f"c-notify: no playable sound for {tool}/{event_name}")
        return 1
    print(f"c-notify: played {tool}/{used_event} -> {path.name}")
    return 0


def cmd_hook(tool: str, event_override: str, payload_arg: str | None, extra: list[str], debug: bool) -> int:
    config = load_config()
    if not bool(config.get("enabled", True)):
        return 0

    payload_text = _resolve_payload_text(payload_arg, extra)
    if tool == "codex":
        normalized, candidates = resolve_codex_events(payload_text, event_override, config)
    else:
        normalized, candidates = resolve_claude_events(payload_text, event_override)

    with state_lock():
        state = load_state()
        sound_path, used_event = try_play_event(tool, candidates, config, state)
        save_state(state)

    if debug:
        print(json.dumps(
            {
                "tool": tool,
                "normalized_event": normalized,
                "candidates": candidates,
                "played_event": used_event,
                "played_file": str(sound_path) if sound_path else "",
            },
            indent=2,
        ))

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="c-notify", description="Event-based sound notifications for Codex and Claude.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("on", help="Enable sound playback")
    sub.add_parser("off", help="Disable sound playback")
    sub.add_parser("toggle", help="Toggle sound playback")
    sub.add_parser("status", help="Show runtime status")

    init_parser = sub.add_parser("init", help="Initialize sound directory tree and README files")
    init_parser.add_argument("--refresh-readmes", action="store_true", help="Rewrite event README.md files")

    events_parser = sub.add_parser("events", help="List known events")
    events_parser.add_argument("--tool", choices=["codex", "claude"], help="Filter to one tool")

    hook_parser = sub.add_parser("hook", help="Hook entrypoint for Codex/Claude")
    hook_parser.add_argument("--tool", required=True, choices=["codex", "claude"], help="Event source tool")
    hook_parser.add_argument("--event", default="", help="Optional explicit event name")
    hook_parser.add_argument("--payload", help="Optional explicit payload JSON/string")
    hook_parser.add_argument("--debug", action="store_true", help="Print resolution details")
    hook_parser.add_argument("extra", nargs="*", help="Extra args; first token is treated as payload when --payload is absent")

    play_parser = sub.add_parser("play", help="Manually play one event folder")
    play_parser.add_argument("--tool", required=True, choices=["codex", "claude"], help="Tool namespace")
    play_parser.add_argument("--event", required=True, help="Event folder name")

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "on":
        return set_enabled(True)
    if args.command == "off":
        return set_enabled(False)
    if args.command == "toggle":
        return cmd_toggle()
    if args.command == "status":
        return cmd_status()
    if args.command == "init":
        return cmd_init(refresh_readmes=bool(args.refresh_readmes))
    if args.command == "events":
        return cmd_events(tool=args.tool)
    if args.command == "play":
        return cmd_play(tool=args.tool, event_name=_slug(args.event))
    if args.command == "hook":
        return cmd_hook(
            tool=args.tool,
            event_override=args.event,
            payload_arg=args.payload,
            extra=args.extra,
            debug=bool(args.debug),
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
