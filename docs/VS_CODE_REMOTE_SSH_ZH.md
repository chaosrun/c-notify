# VS Code Remote SSH

这份说明页专门讲 `c-notify` 在以下场景下的推荐配置：

- 声音应该在你的本机播放
- Codex 或 Claude Code 跑在远端机器上
- 你通过 VS Code Remote SSH 或普通 `ssh` 连接远端

同一台本机可以同时承担两种角色：

- 本机 Codex / Claude 继续直接 `hook` 播放
- 远端 Codex / Claude 通过 `relay -> serve` 回传到本机播放

## 概览

| | 本机 (A) | 远端 (B) |
|---|---|---|
| 角色 | 播放音效，运行 `c-notify serve` | 运行 Codex / Claude Code |
| Hooks | 直接播放 (`hook`) | Relay 模式 (`relay`) |
| 音频文件 | `~/.c-notify/sounds/` | 不需要 |
| SSH | 发起连接，拥有隧道 | 接收反向转发端口 |

SSH reverse tunnel：远端 `127.0.0.1:38765` 回传到本机 `127.0.0.1:38765`。
SSH 配置写在本机。

## 推荐配置

### 1. 本机保持正常本地播放

本机 Codex / Claude 继续用普通直连安装：

```bash
cd /path/to/c-notify
./install.sh
```

不要在本机用 `--remote-endpoint` 重装，除非你有意让本机事件也绕 HTTP。

### 2. 本机启动接收服务

```bash
c-notify serve --listen 127.0.0.1 --port 38765
```

可选 token：

```bash
c-notify serve --listen 127.0.0.1 --port 38765 --token secret-token
```

健康检查：

```bash
curl http://127.0.0.1:38765/healthz
```

### 3. 本机配置 SSH reverse forwarding

编辑本机 `~/.ssh/config`：

```sshconfig
Host my-remote
    HostName your.remote.host
    User your_user
    RemoteForward 127.0.0.1:38765 127.0.0.1:38765
```

VS Code Remote SSH 会复用这份 SSH 配置。

### 4. 远端安装 relay 模式

不带 token：

```bash
cd /path/to/c-notify
./install.sh --remote-endpoint=http://127.0.0.1:38765
```

带 token：

```bash
cd /path/to/c-notify
./install.sh --remote-endpoint=http://127.0.0.1:38765 --remote-token=secret-token
```

这会把远端 hooks 从：

- `c-notify.py hook --tool ...`

改成：

- `c-notify.py relay --tool ... --endpoint http://127.0.0.1:38765`

## SSH 隧道管理

### 多个会话

多个远端 shell 本身没问题，只要它们共享同一条可用的 reverse tunnel。

真正容易冲突的不是 `c-notify` 逻辑，而是 SSH 端口占用：

- 每台远端机器通常约定一个固定 relay 端口，例如 `127.0.0.1:38765`
- 如果多个彼此独立的 SSH 连接都去抢同一个远端转发端口，就可能冲突

推荐做法：

- 每台远端机器固定一个 relay 端口
- 尽量复用 SSH 连接
- 避免手工启动多条互相竞争同一 remote port 的 reverse tunnel

### 专用隧道进程

如果你想让这套东西更稳，建议把 reverse tunnel 从 VS Code 或交互式 shell 会话里拆出来，单独维护。

这种模式下，本机会运行：

- `c-notify serve`
- 一条专门负责 reverse tunnel 的长期 SSH 进程

远端机器仍然把 hook payload 发到：

- `http://127.0.0.1:38765`

只是这个隧道不再依赖某个编辑器窗口或 shell 会话，而是由一条专门的 SSH 进程负责。

本机手工命令示例：

```bash
ssh -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -R 127.0.0.1:38765:127.0.0.1:38765 \
  my-remote
```

本机推荐的 SSH 配置形态：

```sshconfig
Host my-remote
    HostName your.remote.host
    User your_user
```

这样一来，隧道所有权在这条专门的 SSH 进程手里，而不在编辑器会话里。结果是：

- 远端 Codex / Claude hooks 仍然使用同一个 relay endpoint
- 多个远端 shell 可以并存，而不会各自去抢同一个 forwarded port
- tunnel 问题更容易和 hook/播放问题分开排查

重要：

- 对同一台远端机器和同一个端口，要么用按会话 `RemoteForward`，要么用专用隧道进程
- 不要让这两种模式同时去占远端的 `127.0.0.1:38765`

## Token

目前 token 不是自动生成的。

现在需要你显式传入：

```bash
# 本机
c-notify serve --token secret-token

# 远端
./install.sh --remote-endpoint=http://127.0.0.1:38765 --remote-token=secret-token
```

如果只监听 `127.0.0.1`，并且只通过 SSH reverse tunnel 访问，不带 token 也能工作。但如果你未来会接多个远端，建议加 token。

## 自启动

仓库里已经准备好了模板文件：

| | systemd (Linux) | launchd (macOS) |
|---|---|---|
| serve | [`c-notify-serve.service`](../examples/systemd/c-notify-serve.service), [`serve.env.example`](../examples/systemd/serve.env.example) | [`com.c-notify.serve.plist`](../examples/launchd/com.c-notify.serve.plist) |
| tunnel | [`c-notify-tunnel.service`](../examples/systemd/c-notify-tunnel.service), [`tunnel.env.example`](../examples/systemd/tunnel.env.example) | [`com.c-notify.tunnel.plist`](../examples/launchd/com.c-notify.tunnel.plist) |

这些文件只是模板，不会自动安装。

## 排查思路

远端没有声音：

1. 确认本机 receiver 正在运行：

```bash
curl http://127.0.0.1:38765/healthz
```

2. 确认 SSH 会话真的建立了 `RemoteForward`
3. 确认远端安装时用了 `--remote-endpoint`
4. 如果启用了 token，确认两边一致

专用隧道进程已经运行，但远端声音仍然没有回来：

1. 确认这条专门的 SSH 进程确实连上了
2. 确认它占用了预期的远端端口
3. 确认你的编辑器或 shell 会话没有再去创建第二条同端口 `RemoteForward`

本机声音正常，远端没有声音：

- 先查 reverse tunnel
- 再查远端 `install.sh` 生成的 hooks 配置

远端机器提示缺少音频文件：

- 这通常是配置错了
- relay 模式不应要求远端放音频文件
