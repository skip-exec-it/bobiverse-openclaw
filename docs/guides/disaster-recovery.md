# Disaster Recovery

How to recover a bob after host failure — hardware loss, container corruption, or unrecoverable OS state. This guide assumes the host is gone and you need to rebuild from inputs.

---

## What You Have (Recovery Inputs)

| Input | Location | Notes |
|-------|----------|-------|
| Skills | `$CLAWDBOT_HOME/skills/` on shared storage | Authoritative copy, always current |
| Identity files | `$CLAWDBOT_HOME/instances/<Name>/` on shared storage | IDENTITY.md, SOUL.md, role files |
| Memory | `$CLAWDBOT_HOME/instances/<Name>/memory/` on shared storage | MEMORY.md + semantic memory exports if backed up |
| Logs | `$CLAWDBOT_HOME/instances/<Name>/logs/` on shared storage | Preserved |
| Vault key | **Not** on shared storage — must be delivered manually | See step 2 |

---

## What You Lose

These are ephemeral and do not need to be restored:

- **Local state** (cursor positions, PID files, lock files) — auto-rebuilds on first run
- **Conversation sessions** (chat history) — not backed up; new host starts fresh
- **App databases** on local disk — only recoverable if separately snapshotted (e.g., Proxmox backup, external snapshot)

These are not lost (they live on shared storage):

- Identity, persona, role configuration
- Full memory (MEMORY.md and any exported semantic index)
- All logs
- All skills

---

## Recovery Steps

### Step 1: Provision a Fresh Host

Stand up a new Linux host (LXC container or VM) with the same hostname or a replacement hostname, and follow the provisioning guide:

```
docs/guides/provisioning-a-bob.md
```

Work through all steps up to (but not including) the fleet-sync step. Do not generate a new vault key — you will restore the original in step 2.

---

### Step 2: Restore the Vault Key

The vault key must be delivered manually. It is never stored on shared storage.

Retrieve the key from wherever it was backed up (password manager, offline key store, another trusted administrator). Write it to the new host:

```bash
echo "<64-char-hex-key>" > /home/bob/.openclaw-vault-key
chmod 600 /home/bob/.openclaw-vault-key
chown bob:bob /home/bob/.openclaw-vault-key
```

Verify:
```bash
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py list
```

You should see vault keys without error. If the vault returns decryption errors, the key is wrong.

---

### Step 3: Run Fleet-Sync

Mirror skills and shared configuration to the local workspace:

```bash
/home/bob/.openclaw/scripts/fleet-sync.sh
```

This populates the local skills directory from shared storage. Run it once now; the scheduled cron (installed in a later step) will keep it current.

---

### Step 4: Restore Instance Files from Shared Storage

Copy the instance's working directory from shared storage:

```bash
cp -r $CLAWDBOT_HOME/instances/<Name>/ \
      /home/bob/.openclaw/workspace/instances/<Name>/
```

This includes IDENTITY.md, SOUL.md, role files, and any logs stored under the instance path.

If memory exports exist:
```bash
cp -r $CLAWDBOT_HOME/instances/<Name>/memory/ \
      /home/bob/.openclaw/workspace/memory/
```

If the semantic index was not exported, the bob starts with MEMORY.md only and rebuilds the vector index from scratch as it runs.

---

### Step 5: Restart Gateway and SCUT Listener

Restart gateway pairing (the new host has a new device identity):

```bash
openclaw gateway reset
openclaw gateway pair
```

Start and verify the SCUT listener:

```bash
systemctl start scut-listener
systemctl status scut-listener
```

---

### Step 6: Verify Communications

Send a test message from another instance or the owner's terminal:

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py send \
  --to <Name> --message "recovery check"
```

On the recovered host:

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py check
```

Verify: message received, instance name reported correctly, no vault errors in logs.

---

### Step 7: Run Protocol Inspection

Once the instance is stable, run a full inspection against FLEET-PROTOCOL.md. File the completed report:

```
$CLAWDBOT_HOME/instances/<Name>/inspection-reports/recovery-<YYYY-MM-DD>.md
```

Resolve any FAIL ratings before the instance returns to active duties.

---

## bmail-db Recovery (PostgreSQL Host Lost)

If the PostgreSQL host backing the bmail database is lost, SCUT continues to deliver via the JSONL fallback. Messages are not lost — they queue locally. Postgres only needs to be restored for durability and message history.

**Stand up a fresh PostgreSQL host:**

```bash
# Install Postgres (version must match original or newer)
apt install postgresql

# Create database and user
sudo -u postgres createdb <db-name>
sudo -u postgres createuser <db-user>
sudo -u postgres psql -c "ALTER USER <db-user> PASSWORD '<password>';"
```

**Recreate the messages table:**

The schema is documented in `docs/reference/comms-model.md`. Apply it:

```bash
sudo -u postgres psql -d <db-name> -f /path/to/comms-schema.sql
```

**Update vault keys on all bobs to point to the new host:**

On each bob:
```bash
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/host <new-postgres-host>
python3 $CLAWDBOT_HOME/skills/vault/scripts/vault.py set db/password <new-password>
```

**Replay JSONL outbox (optional):**

JSONL fallback files on shared storage serve as the recovery source for message history. If you need to import them into the new Postgres, the comms.py script may have a `--import-jsonl` option — check its help output:

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py --help
```

**Verify:**

```bash
python3 $CLAWDBOT_HOME/skills/scut/scripts/comms.py health
```

Should report Postgres connected.

---

## Recovery Checklist

| Step | Done |
|------|------|
| Fresh host provisioned | |
| Vault key restored manually (not from shared storage) | |
| Fleet-sync run | |
| Instance files copied from shared storage | |
| Memory files copied (or noted as rebuilding) | |
| Gateway device pairing regenerated | |
| SCUT listener running | |
| Comms verified (send/receive test) | |
| No vault errors in logs | |
| Protocol inspection filed | |
