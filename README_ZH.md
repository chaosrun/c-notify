# c-notify

`c-notify` 是一个面向 **Codex** 与 **Claude Code** 的本地 Hook 音效路由器。
当事件触发时，它会从 `~/.c-notify/sounds/<tool>/<event>/` 随机播放一个音频文件。

音频文件由用户自行放入，仓库本身不内置音频资产。

<p align="center">
  <a href="README.md">📖 English</a>&nbsp;&nbsp;|&nbsp;&nbsp;<a href="docs/VS_CODE_REMOTE_SSH_ZH.md">🔗 Remote SSH 说明</a>
</p>

## 功能

- 按工具分命名空间（`codex` 与 `claude`），事件集合可不同
- 按事件目录随机播放
- 便携总开关：`on / off / toggle / status`
- 独立权限请求音效开关：`permission on / off / toggle / status`
- 支持 macOS / Linux 播放后端
- 自动初始化事件目录与中英双语 `README.md`
- 支持 Codex `SessionStart`、`UserPromptSubmit`、`PermissionRequest` 与 `PreCompact` hooks
- 支持可选的 remote relay 模式，适用于 VS Code Remote SSH 等远程开发场景
- Codex 路由是确定性的：`agent-turn-complete` 直接映射到 `task-complete`

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
- 写入/更新 Codex hooks 文件 `~/.codex/hooks.json`
- 写入/更新 Claude 的 `~/.claude/settings.json`

常用参数：

```bash
./install.sh --no-codex
./install.sh --no-claude
./install.sh --no-path
./install.sh --bin-dir=/custom/bin
./install.sh --remote-endpoint=http://127.0.0.1:38765
./install.sh --remote-endpoint=http://127.0.0.1:38765 --remote-token=secret-token
```

## 音效目录

Codex：

- `~/.c-notify/sounds/codex/task-acknowledge/`（来自 Codex `UserPromptSubmit`）
- `~/.c-notify/sounds/codex/task-complete/`
- `~/.c-notify/sounds/codex/permission-needed/`（来自 Codex `PermissionRequest`）
- `~/.c-notify/sounds/codex/task-error/`
- `~/.c-notify/sounds/codex/context-compact/`（来自 Codex `PreCompact`）
- `~/.c-notify/sounds/codex/resource-limit/`
- `~/.c-notify/sounds/codex/session-start/`（来自 Codex `SessionStart`）

Claude：

- `~/.c-notify/sounds/claude/session-start/`
- `~/.c-notify/sounds/claude/session-end/`（可选）
- `~/.c-notify/sounds/claude/subagent-start/`（可选）
- `~/.c-notify/sounds/claude/task-acknowledge/`
- `~/.c-notify/sounds/claude/task-complete/`
- `~/.c-notify/sounds/claude/permission-needed/`
- `~/.c-notify/sounds/claude/context-compact/`
- `~/.c-notify/sounds/claude/resource-limit/`

## Hook 配置

### Codex（`~/.codex/config.toml` 与 `~/.codex/hooks.json`）

`config.toml` 保留 `notify` 负责完成音效，并开启 hooks 引擎：

```toml
notify = ["python3", "/ABSOLUTE/PATH/TO/c-notify/c-notify.py", "hook", "--tool", "codex"]

[features]
hooks = true
```

`hooks.json` 接入 `SessionStart`、`UserPromptSubmit`、`PermissionRequest` 与 `PreCompact`：

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

说明：

- Codex `notify` 在当前正常链路下主要是 `agent-turn-complete`。
- Codex 不做消息语义推断；`agent-turn-complete` 总是路由到 `task-complete`。
- Codex hooks 当前用于 `SessionStart`、`UserPromptSubmit`、`PermissionRequest` 与 `PreCompact`。
- Codex 新增或变更 hook 后可能要求在 TUI 里 review；当 Codex 提示时，打开 `/hooks` 并批准 `c-notify` 条目。
- `UserPromptSubmit` 会映射到 `task-acknowledge`。
- `PermissionRequest` 会映射到 `permission-needed`。
- `PreCompact` 会映射到 `context-compact`；`PostCompact` 可识别为同一类别，但默认不安装，避免 compact 前后连响两次。
- 对同一个 Codex `session_id`，紧跟在 `SessionStart` 后的首个 `UserPromptSubmit` 会被抑制，以避免新会话或恢复会话时连播两次声音。
- `Stop` 不写入 `hooks.json`；完成音效已经由 `notify` 负责，再接 `Stop` 会重复播放。
- `PreToolUse` 与 `PostToolUse` 默认不写入，因为它们是高频工具事件。
- Codex 的 `task-error` 与 `resource-limit` 当前仍属于显式/手动类别，除非未来 Codex 原生发出对应事件。
- 示例文件见 [`examples/codex-config.toml`](examples/codex-config.toml) 与 [`examples/codex-hooks.json`](examples/codex-hooks.json)。

### Claude Code（`~/.claude/settings.json`）

每个事件使用相同的命令，只有事件名和 `matcher` 不同：

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

其余事件使用同样的结构：

| 事件 | `matcher` |
|------|-----------|
| `SessionStart` | `""` |
| `SessionEnd` | `""` |
| `SubagentStart` | `""` |
| `UserPromptSubmit` | `""` |
| `Stop` | `""` |
| `PermissionRequest` | `""` |
| `PreCompact` | `""` |

`Notification` 不再注册；权限提示只由 `PermissionRequest` 触发。

## Remote SSH

remote 模式是可选能力。不做任何额外配置时，`c-notify` 仍然只是本机播放工具，现有行为不变。

当 Codex 或 Claude 跑在远端机器上、但你希望声音在本机响起时，可使用 remote 模式。

1. 在本机启动接收服务：

```bash
c-notify serve --listen 127.0.0.1 --port 38765
```

2. 在本机的 SSH 配置里，为该远端主机加反向转发：

```sshconfig
Host my-remote
    HostName your.remote.host
    User your_user
    RemoteForward 127.0.0.1:38765 127.0.0.1:38765
```

3. 在远端机器上安装 relay 版 hooks，而不是本地直接播放版：

```bash
./install.sh --remote-endpoint=http://127.0.0.1:38765
```

4. 可选：在两端都加 token 保护：

```bash
# 本机
c-notify serve --listen 127.0.0.1 --port 38765 --token secret-token

# 远端
./install.sh --remote-endpoint=http://127.0.0.1:38765 --remote-token=secret-token
```

说明：

- 只有显式传入 `--remote-endpoint` 时，`install.sh` 才会切换成 relay 模式。
- 本机安装默认仍然是直接播放模式。
- 接收服务提供 `GET /healthz`，并接收 `POST /hook/codex` 与 `POST /hook/claude`。
- 完整配置说明见 [`docs/VS_CODE_REMOTE_SSH_ZH.md`](docs/VS_CODE_REMOTE_SSH_ZH.md)

相关文件：

| | Hook 示例 | 自启动 (systemd) | 自启动 (launchd) |
|---|---|---|---|
| Codex | [`codex-config-remote.toml`](examples/codex-config-remote.toml), [`codex-hooks-remote.json`](examples/codex-hooks-remote.json) | [`c-notify-serve.service`](examples/systemd/c-notify-serve.service) | [`com.c-notify.serve.plist`](examples/launchd/com.c-notify.serve.plist) |
| Claude | [`claude-hooks-remote.json`](examples/claude-hooks-remote.json) | [`c-notify-tunnel.service`](examples/systemd/c-notify-tunnel.service) | [`com.c-notify.tunnel.plist`](examples/launchd/com.c-notify.tunnel.plist) |

## 常用命令

安装：

```bash
./install.sh
./c-notify init
./c-notify init --refresh-readmes
```

控制：

```bash
./c-notify on
./c-notify off
./c-notify toggle
./c-notify status
./c-notify permission off
./c-notify permission on
./c-notify permission toggle
./c-notify permission status
./c-notify events
./c-notify events --tool codex
./c-notify events --tool claude
```

手动播放：

```bash
./c-notify play --tool claude --event task-complete
./c-notify play --tool codex --event task-acknowledge
```

调试：

```bash
./c-notify hook --tool codex --event session-start --debug
./c-notify hook --tool codex --debug
./c-notify hook --tool claude --debug
tail -n 40 ~/.c-notify/logs/hook-events.jsonl
```

远程：

```bash
./c-notify serve --listen 127.0.0.1 --port 38765
./c-notify relay --tool codex --endpoint http://127.0.0.1:38765 --debug
```

## 配置文件

运行时配置：

- `~/.c-notify/config.json`
- `~/.c-notify/state.json`
- `~/.c-notify/logs/hook-events.jsonl`

可选覆盖：

- 使用 `C_NOTIFY_HOME=/custom/path` 可整体迁移 config/state/sounds 根目录。
- 使用 `C_NOTIFY_INSTALL_HOME=/custom/home` 可覆盖 `install.sh` 的安装目标根目录。
- 使用 `C_NOTIFY_REMOTE_ENDPOINT=http://127.0.0.1:38765` 可为 `relay` 与 remote 安装提供默认接收地址。
- 使用 `C_NOTIFY_REMOTE_TOKEN=secret-token` 可让 `serve`、`relay` 与 remote 安装复用同一个 token。

主要字段：

- `enabled`：总开关
- `sound_root`：默认 `~/.c-notify/sounds`
- `volume`：播放音量（具体效果由后端决定）
- `extensions`：允许的音频扩展名
- `prevent_overlap`：前一个音频进程未结束时是否跳过新播放
- `cooldown_seconds` / `cooldown_by_event`：节流设置
- `permission_sound_enabled`：默认 `true`；为 `false` 时，`permission-needed` 事件只记录日志，不播放声音
- `hook_strict_exit`：默认 `false`；开启后 unmapped/no-sound 会返回非零退出码

Hook 调试日志：

- `~/.c-notify/logs/hook-events.jsonl` 会记录最近的 Codex / Claude hook 调用
- payload 文本会做截断，避免单条日志过大
- 会自动轮转：`256 KiB x 4 files`

## 平台支持

- macOS：`afplay`
- Linux：`pw-play`、`paplay`、`ffplay`、`aplay`（按顺序回退）

Windows 支持在首版范围之外。
