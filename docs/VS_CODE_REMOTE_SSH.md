# VS Code Remote SSH

This guide covers the recommended `c-notify` setup when:

- your local machine should play the sound
- Codex or Claude Code runs on a remote machine
- you connect through VS Code Remote SSH or plain `ssh`

The same local machine can serve both:

- local Codex / Claude sessions via direct `hook`
- remote Codex / Claude sessions via `relay -> serve`

## Roles

Machine A, local machine:

- stores the audio files under `~/.c-notify/sounds/`
- runs `c-notify serve`
- keeps local Codex / Claude hooks in direct-playback mode
- initiates the SSH connection to the remote host

Machine B, remote machine:

- runs Codex or Claude Code
- installs `c-notify` hooks in relay mode
- does not need audio files

## Audio Location

In remote mode, audio files belong on the machine that runs `c-notify serve`.

Default location:

- `~/.c-notify/sounds/`

The remote machine only forwards hook payloads. It does not need sound assets unless you also want direct local playback there.

## SSH Direction

Run the SSH command on the local machine.

The recommended tunnel is a reverse tunnel:

- remote `127.0.0.1:38765`
- forwards back to local `127.0.0.1:38765`

That is why the SSH config belongs on the local machine, not the remote one.

## Recommended Setup

### 1. Local machine: keep normal local playback

Your local Codex / Claude install should remain the normal direct-playback install:

```bash
cd /path/to/c-notify
./install.sh
```

Do not reinstall the local machine with `--remote-endpoint` unless you intentionally want even local hooks to go through HTTP.

### 2. Local machine: start the receiver

```bash
c-notify serve --listen 127.0.0.1 --port 38765
```

Optional token:

```bash
c-notify serve --listen 127.0.0.1 --port 38765 --token secret-token
```

Health check:

```bash
curl http://127.0.0.1:38765/healthz
```

### 3. Local machine: add SSH reverse forwarding

Edit local `~/.ssh/config`:

```sshconfig
Host my-remote
    HostName your.remote.host
    User your_user
    RemoteForward 127.0.0.1:38765 127.0.0.1:38765
```

VS Code Remote SSH reuses this SSH configuration.

### 4. Remote machine: install relay mode

Without token:

```bash
cd /path/to/c-notify
./install.sh --remote-endpoint=http://127.0.0.1:38765
```

With token:

```bash
cd /path/to/c-notify
./install.sh --remote-endpoint=http://127.0.0.1:38765 --remote-token=secret-token
```

This changes remote hooks from:

- `c-notify.py hook --tool ...`

to:

- `c-notify.py relay --tool ... --endpoint http://127.0.0.1:38765`

## Coexisting Local And Remote Usage

This is the intended shape:

- Machine A local Codex / Claude:
  direct playback via `hook`
- Machine B remote Codex / Claude:
  relay back to Machine A via `serve`

That means one machine can be both:

- a normal local playback machine
- a receiver for one or more remote machines

## Multiple SSH Sessions

Multiple remote shells are fine as long as they reuse one working reverse tunnel for the same remote host.

The actual conflict risk is not `c-notify` logic. It is SSH port binding:

- each remote host typically uses one fixed relay port such as `127.0.0.1:38765`
- multiple independent SSH connections that all try to claim the same remote forwarded port can conflict

Recommended practice:

- one fixed remote relay port per remote host
- prefer SSH connection reuse
- avoid manually creating several independent reverse tunnels that all compete for the same remote port

## Dedicated Tunnel Process

If you want a more stable setup, keep the reverse tunnel outside VS Code and outside interactive shell sessions.

In that mode, the local machine runs:

- `c-notify serve`
- one separate long-lived SSH process that owns the reverse tunnel

The remote machine still sends hook payloads to:

- `http://127.0.0.1:38765`

but the tunnel is now provided by a dedicated SSH process instead of whichever shell or editor session happened to connect first.

Manual example on the local machine:

```bash
ssh -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -R 127.0.0.1:38765:127.0.0.1:38765 \
  my-remote
```

Recommended SSH config shape on the local machine:

```sshconfig
Host my-remote
    HostName your.remote.host
    User your_user
```

The tunnel owner becomes the dedicated SSH process, not the editor session. That means:

- remote Codex / Claude hooks can keep using the same relay endpoint
- several remote shells can coexist without each trying to claim the same forwarded port
- tunnel failures are easier to isolate from hook or playback problems

Important:

- use either per-session `RemoteForward` or a dedicated tunnel process for the same remote host and port
- do not let both patterns try to own `127.0.0.1:38765` on the remote side at the same time

## Token

Token generation is currently manual.

Today you set it explicitly:

```bash
# local machine
c-notify serve --token secret-token

# remote machine
./install.sh --remote-endpoint=http://127.0.0.1:38765 --remote-token=secret-token
```

If you listen only on `127.0.0.1` and access it only through SSH reverse tunnels, token-less operation is still acceptable. A token is recommended when you expect more than one remote source or want cleaner separation.

## Autostart

Prepared templates are included in this repository:

| | systemd (Linux) | launchd (macOS) |
|---|---|---|
| serve | [`c-notify-serve.service`](../examples/systemd/c-notify-serve.service), [`serve.env.example`](../examples/systemd/serve.env.example) | [`com.c-notify.serve.plist`](../examples/launchd/com.c-notify.serve.plist) |
| tunnel | [`c-notify-tunnel.service`](../examples/systemd/c-notify-tunnel.service), [`tunnel.env.example`](../examples/systemd/tunnel.env.example) | [`com.c-notify.tunnel.plist`](../examples/launchd/com.c-notify.tunnel.plist) |

These files are templates only. They are not installed automatically.

## Troubleshooting

No sound from a remote host:

1. Confirm local receiver is running:

```bash
curl http://127.0.0.1:38765/healthz
```

2. Confirm the SSH session actually established `RemoteForward`
3. Confirm the remote install used `--remote-endpoint`
4. Confirm the token matches on both sides if token mode is enabled

Dedicated tunnel process is running but remote sounds still do not arrive:

1. Confirm the dedicated SSH process is connected
2. Confirm it owns the intended remote port
3. Confirm your editor or shell session is not also trying to create a second `RemoteForward` for the same port

Local sounds work but remote sounds do not:

- check the reverse tunnel first
- then check the remote hook wiring generated by `install.sh`

Remote machine asks for audio files:

- that is a configuration mistake
- relay mode should not need remote sound assets
