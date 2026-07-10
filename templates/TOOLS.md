# TOOLS.md — Local Notes

Skills define *how* tools work. This file is for *your* specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- SSH hosts and aliases you use frequently
- Camera names and locations (if you have home automation)
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Local service URLs and ports
- Anything environment-specific that skills shouldn't hardcode

## Examples

```markdown
### SSH Hosts
- proxmox      → 192.168.1.1, root (via vault key)
- nas          → 192.168.1.50, admin

### Local Services
- home-assistant → http://192.168.1.100:8123
- adguard        → http://192.168.1.108

### TTS
- Preferred voice: "Nova"
- Default speaker: Living room
```

## Why Separate?

Skills are shared across the fleet. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

*Add whatever helps you do your job. This is your cheat sheet.*
