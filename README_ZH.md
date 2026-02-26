# c-notify

`c-notify` 是一个面向 **Codex** 与 **Claude Code** 的本地 Hook 音效路由器。
当事件触发时，它会从 `~/.c-notify/sounds/<tool>/<event>/` 随机播放一个音频文件。

音频文件由用户自行放入，仓库本身不内置音频资产。

## 功能

- 按工具分命名空间（`codex` 与 `claude`），事件集合可不同
- 按事件目录随机播放
- 便携总开关：`on / off / toggle / status`
- 支持 macOS / Linux 播放后端
- 自动初始化事件目录与中英双语 `README.md`
- 对 Codex `agent-turn-complete` 支持关键词推断事件分类

## 快速开始

```bash
cd c-notify
chmod +x c-notify c-notify.py
./c-notify init
./c-notify status
./c-notify events
```

## 一键安装

```bash
cd c-notify
chmod +x install.sh
./install.sh
```

`install.sh` 会自动执行：

- 安装 `~/.local/bin/c-notify`（符号链接）
- 在你的 shell rc 文件追加 PATH 块（zsh 用 `~/.zshrc`，bash 用 `~/.bashrc`/`~/.bash_profile`）
- 写入/更新 Codex 的 `~/.codex/config.toml`
- 写入/更新 Claude 的 `~/.claude/settings.json`

常用参数：

```bash
./install.sh --no-codex
./install.sh --no-claude
./install.sh --no-path
./install.sh --bin-dir=/custom/bin
```

核心类别（Codex）：

- `~/.c-notify/sounds/codex/task-complete/`
- `~/.c-notify/sounds/codex/permission-needed/`
- `~/.c-notify/sounds/codex/task-error/`
- `~/.c-notify/sounds/codex/context-compact/`
- `~/.c-notify/sounds/codex/resource-limit/`
- `~/.c-notify/sounds/codex/session-start/`（可选/手动触发）

核心类别（Claude）：

- `~/.c-notify/sounds/claude/session-start/`
- `~/.c-notify/sounds/claude/session-end/`（可选）
- `~/.c-notify/sounds/claude/subagent-start/`（可选）
- `~/.c-notify/sounds/claude/task-acknowledge/`
- `~/.c-notify/sounds/claude/task-complete/`
- `~/.c-notify/sounds/claude/permission-needed/`
- `~/.c-notify/sounds/claude/task-error/`
- `~/.c-notify/sounds/claude/context-compact/`
- `~/.c-notify/sounds/claude/resource-limit/`

## Hook 配置

### Codex（`~/.codex/config.toml`）

```toml
notify = ["python3", "/ABSOLUTE/PATH/TO/c-notify/c-notify.py", "hook", "--tool", "codex"]
```

说明：

- Codex 目前主要通过 `notify` 发送 `agent-turn-complete`。
- 若你的链路存在 `approval-requested`，会映射到 `permission-needed`。

### Claude Code（`~/.claude/settings.json`）

可为多个事件统一使用同一条命令：

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

## 事件覆盖范围

查看当前内置事件：

```bash
./c-notify events
./c-notify events --tool codex
./c-notify events --tool claude
```

## 常用命令

```bash
./install.sh
./c-notify init
./c-notify init --refresh-readmes
./c-notify on
./c-notify off
./c-notify toggle
./c-notify status
./c-notify events --tool claude
./c-notify play --tool claude --event task-complete
./c-notify hook --tool codex --debug
./c-notify hook --tool claude --debug
```

## 配置文件

运行时配置：

- `~/.c-notify/config.json`

可选覆盖：

- 使用 `C_NOTIFY_HOME=/custom/path` 可整体迁移 config/state/sounds 根目录。
- 使用 `C_NOTIFY_INSTALL_HOME=/custom/home` 可覆盖 `install.sh` 的安装目标根目录。

主要字段：

- `enabled`：总开关
- `sound_root`：默认 `~/.c-notify/sounds`
- `volume`：播放音量（具体效果由后端决定）
- `extensions`：允许的音频扩展名
- `prevent_overlap`：前一个音频进程未结束时是否跳过新播放
- `cooldown_seconds` / `cooldown_by_event`：节流设置
- `codex_keywords`：Codex 文本关键词推断规则（`context-compact`、`permission-needed`、`task-error`、`resource-limit`）

## 平台支持

- macOS：`afplay`
- Linux：`pw-play`、`paplay`、`ffplay`、`aplay`（按顺序回退）

Windows 支持在首版范围之外。
