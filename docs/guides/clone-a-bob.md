# Cloning a Bob

Cloning an existing LXC bob is the fastest way to spin up a new instance. The clone inherits the vault key and base configuration automatically — no manual key distribution needed.

Use this when you have a healthy, clean source bob and want a new instance with the same skill set and base setup. For a clean-slate provision (no source bob, or deliberately starting fresh), see `provisioning-a-bob.md`.

---

## Why Clone

A full LXC clone copies `/home/bob/` — including `~/.openclaw-vault-key`. This means the new instance has working vault access from the moment it boots, without any manual key handling.

What the clone also inherits (and must be updated):
- Instance name (embedded in `openclaw.json` and systemd units)
- Gateway device pairing (needs to be regenerated for the new host)
- Memory index (should be reset — it contains the source bob's memories)

---

## Step 1: Clone the LXC Container

On the Proxmox host, as root:

```bash
pct clone <source-vmid> <new-vmid> --full true --hostname <new-hostname>
```

Example:
```bash
pct clone 103 107 --full true --hostname tkd04ai
```

`--full true` creates a full independent copy of the disk, not a linked clone. Required — linked clones share the base layer and can cause drift.

After cloning:
```bash
pct start <new-vmid>
pct status <new-vmid>
```

---

## Step 2: Set the Hostname

If Proxmox did not update the in-guest hostname (verify with `hostname` inside the container), fix it:

```bash
pct exec <new-vmid> -- bash -c "hostnamectl set-hostname <new-hostname>"
pct exec <new-vmid> -- bash -c "echo '<new-hostname>' > /etc/hostname"
```

Also update `/etc/hosts` inside the container to replace the old hostname:

```bash
pct exec <new-vmid> -- sed -i 's/<old-hostname>/<new-hostname>/g' /etc/hosts
```

---

## Step 3: Set OPENCLAW_INSTANCE in the systemd Unit

The systemd unit override is the authoritative source of `OPENCLAW_INSTANCE` for the daemon. The shell profile alone is not enough — the daemon does not inherit interactive shell environment.

Inside the new container, edit the SCUT listener unit (or create a drop-in override):

```bash
systemctl edit scut-listener
```

Add:
```ini
[Service]
Environment=OPENCLAW_INSTANCE=NewBobName
```

Reload and restart:
```bash
systemctl daemon-reload
systemctl restart scut-listener
```

Also update the OpenClaw main service if it has its own unit.

---

## Step 4: Update openclaw.json

Edit `/home/bob/.openclaw/openclaw.json` inside the new container:

```json
{
  "instance": "NewBobName",
  "port": 3101,
  "clawdbotHome": "/mnt/clawdbot-home"
}
```

Update:
- `instance` — the new bob's name
- `port` — if this host shares a network segment with the source bob and ports need to be distinct

---

## Step 5: Regenerate Gateway Device Pairing

The gateway device pairing is host-specific. The clone carries the source bob's pairing, which will conflict. Regenerate it:

```bash
openclaw gateway reset
openclaw gateway pair
```

Follow the QR/setup-code flow to complete pairing. The new instance now has its own independent gateway identity.

---

## Step 6: Reset the Memory Index

The cloned memory index contains the source bob's memories. Start fresh:

```bash
openclaw memory reset
```

This wipes the local vector index. The new bob starts with no semantic memories. Its `MEMORY.md` (see next step) becomes the bootstrap.

---

## Step 7: Update IDENTITY.md and MEMORY.md

The clone carries the source bob's identity files. Replace them:

```bash
# Inside the new container, or via shared storage path for this instance:
cp $CLAWDBOT_HOME/templates/IDENTITY.md \
   /home/bob/.openclaw/workspace/instances/NewBobName/IDENTITY.md

cp $CLAWDBOT_HOME/templates/MEMORY.md \
   /home/bob/.openclaw/workspace/memory/MEMORY.md
```

Fill in both files with the new bob's name, role, host, IP, and any known facts about their operating context.

---

## Step 8: First Heartbeat as New Identity

Start (or restart) OpenClaw:

```bash
openclaw restart
```

From another bob or the owner's terminal, send a ping:

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py send \
  --to NewBobName --message "ping — are you up?"
```

Check the new instance received it:

```bash
# SSH into the new container:
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py check
```

The new instance should report its name correctly (not the source bob's name) in any response or log output.

---

## Common Gotcha: root→bob Migration Artifact

A bob that was originally provisioned as `root` and later migrated to run as `bob` may have stale `/root/.openclaw` paths embedded in `sessions.json`. These cause silent failures when the daemon tries to load session state.

**Check for it:**

```bash
grep -c '/root/\.openclaw' /home/bob/.openclaw/agents/main/sessions/sessions.json
```

- `0` = clean, no action needed
- Any positive number = stale paths present

**Fix:**

```bash
sed -i 's|/root/\.openclaw|/home/bob/.openclaw|g' \
  /home/bob/.openclaw/agents/main/sessions/sessions.json
```

Restart OpenClaw after the fix.

---

## Post-Clone Checklist

| Step | Done |
|------|------|
| Container cloned with `--full true` | |
| Hostname updated in-guest | |
| `OPENCLAW_INSTANCE` set in systemd unit | |
| `openclaw.json` updated (instance name, port) | |
| Gateway device pairing regenerated | |
| Memory index reset | |
| `IDENTITY.md` replaced with new bob's details | |
| `MEMORY.md` seeded for new instance | |
| root→bob migration artifact check run | |
| First heartbeat sent and received | |
| Protocol inspection filed | |
