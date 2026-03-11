## Introduction

Virexa is a professional-grade Discord moderation and management platform. It combines a FastAPI backend, a modern web dashboard, and a powerful Discord bot so you can run your server with the same discipline as a SaaS product.

!!! note "Improving this guide"
    Hosting these docs from a Git repository? Expose an “Edit this page” link so your team can propose improvements via pull requests.

---

## What Is Virexa?

> Virexa centralizes server management into a single dashboard, backed by a typed FastAPI API.

At a high level, Virexa consists of:

1. **FastAPI Application**  
   Hosts the dashboard UI, REST endpoints, and WebSocket connections (for example, live logs).

2. **Discord Bot**  
   Connects to your servers, listens for events, and executes moderation, logging, and automation actions based on your configuration.

3. **Database Layer**  
   Persists servers, users, logs, configuration, and events so that state is durable across restarts and updates.

4. **Web Dashboard**  
   A SaaS-style interface for configuring moderation, logging, backups, role behavior, and more without memorizing command flags.

---

## Why Use Virexa Instead of a Simple Bot?

1. **Dashboard-First Workflow**  
   Admins log into the dashboard, pick a server, and adjust configuration with forms, toggles, and checklists instead of raw commands.

2. **FastAPI Architecture**  
   The backend is built on FastAPI, making routes predictable and easy to extend. The dashboard uses the same public endpoints exposed to you.

3. **Structured Moderation**  
   Moderation events are case-tracked and logged, making it simple to audit who did what, when, and why.

4. **Deep Logging & Analytics**  
   Rich logs and events are stored in the database and streamed in real time to the UI so you can catch issues early.

5. **Scales with Your Server**  
   Whether you're running a small community or a very large one, Virexa’s architecture and persistence are designed to scale.

---

## Core Capabilities at a Glance

- **Moderation System**: Case IDs, escalation rules, and structured staff workflows.  
- **Backup & Restore**: Protects your server configuration from accidents or malicious changes.  
- **Advanced Logging**: Tracks key Discord events for transparency and audits.  
- **Role Management**: Auto-roles, sticky roles, and bulk operations for large communities.  
- **AFK & Reminders**: Keeps important information visible and follow-ups from being forgotten.  
- **Boards & Counters**: Highlight community activity and server growth visually.  
- **FastAPI Endpoints**: Clean REST and WebSocket interfaces that also power custom integrations.

For a feature-by-feature breakdown, see the [Core Features overview](../core-features/overview.md).

---

## How the Dashboard & API Work Together

The dashboard is just a client of the same API surface you can integrate with:

- `GET /api/me` — Returns the currently authenticated Discord user.  
- `GET /api/guilds` — Lists guilds where the user has administrator permissions.  
- `GET /api/logs` — Fetches recent log entries for use in tables and charts.  
- `WEBSOCKET /ws/logs` — Streams logs in real time to the dashboard.  
- `POST /settings` — Saves server-specific configuration (prefix, log channels, enabled events).

FastAPI also exposes interactive API docs at `/api/docs` and `/api/redoc`, but this site is the **primary** curated documentation for how Virexa is intended to be used.

---

## Ready to Start?

Getting Virexa running for your team is straightforward:

1. **Deploy or run the FastAPI app** (for example, with `uvicorn`).  
2. **Invite the bot** to your Discord server.  
3. **Log in with Discord** at your dashboard URL.  
4. **Configure basics** such as log channels, moderation preferences, and roles.

See the [Setup Guide](setup.md) for a detailed, step-by-step walkthrough.
