# Bobiverse — OpenClaw Fleet Framework

> **"Build your own fleet of OpenClaw agents working in a unified ecosystem."**

This repository contains the complete methodology, protocol, templates, and bootstrap tooling for running a multi-agent fleet on [OpenClaw](https://openclaw.ai) — a cooperative team of AI agents that share skills, communicate autonomously, and persist knowledge across sessions and hardware failures.

## What is a Fleet?

A **fleet** is a set of named AI agent instances (called **bobs**) that:

- Run on different hosts (Linux LXCs, VMs, Windows workstations)
- Share a common skill library and protocol
- Communicate with each other autonomously via bmail (PostgreSQL + JSONL fallback) and SCUT (real-time wake)
- Maintain individual identity, memory, and personality that accumulates over time
- Survive the loss of any single host without losing knowledge

Each bob is a full OpenClaw agent with its own role focus — but every bob is capable of any task. Roles shape development; they don't gate what a bob can do.

## What's in This Repo

| Directory | Contents |
|-----------|----------|
| [`docs/architecture/`](docs/architecture/) | How the fleet is structured: storage model, comms, model policy |
| [`docs/concepts/`](docs/concepts/) | Core ideas: identity, heartbeat, handoff, inspection, waivers |
| [`docs/guides/`](docs/guides/) | Step-by-step: provision a bob, clone a bob, first heartbeat, recovery |
| [`docs/protocol/`](docs/protocol/) | The Fleet Protocol — 14 Articles governing all fleet behavior |
| [`templates/`](templates/) | Drop-in starter files for every new bob |
| [`bootstrap/`](bootstrap/) | Scripts to stand up a bob from scratch (Linux + Windows) |
| [`skills/`](skills/) | Fleet-standard portable skills: vault, scut, fleet-sync, image-gen |

## Quick Start

1. Read [`PHILOSOPHY.md`](PHILOSOPHY.md) — nine principles behind every decision
2. Follow [`QUICKSTART.md`](QUICKSTART.md) — from zero to a running bob
3. Read [`docs/protocol/fleet-protocol.md`](docs/protocol/fleet-protocol.md) — the full standard your fleet will operate under

## Design Philosophy

The fleet is built on a few hard-won lessons:

- **OneDrive (or any shared sync) is cold-standby, not live substrate.** Running processes write local; heartbeats push to shared storage for redundancy.
- **Bobs communicate autonomously.** A message that is read but not acted on is a comms failure regardless of transport health.
- **Identity is load-bearing.** A bob that loses its identity mid-session produces incoherent output that looks like the model is broken. Anchor identity explicitly.
- **Free models first.** Paid model access is a case-by-case grant, not the default. The fleet must function on free-tier providers.
- **Every bob is a rifleman.** Roles focus development; any bob can take any assignment.

## Related Repos

- [`bobiverse-fleet`](https://github.com/skip-exec-it/bobiverse-fleet) *(private)* — Live fleet instance data (identity, memory, logs). Never public.

## Version

Fleet Protocol: **v1.8.0**
Framework: **v1.0.0**
