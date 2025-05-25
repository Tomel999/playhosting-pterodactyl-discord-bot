# 🎮 PlayHosting Pterodactyl Discord Bot

A Discord bot for managing **Pterodactyl** game servers directly from Discord using **slash commands**.

## ✨ Features

- **Pterodactyl Configuration** — Set your panel URL and API key per Discord guild.
- **Default Server Setting** — Define a default server for simplified command usage.
- **Server Aliases** — Create friendly aliases for server UUIDs.
- **Server Status** — Get live metrics: CPU, RAM, Disk, Network.
- **Power Actions** — Start, stop, restart, or force-stop servers.
- **Send Commands** — Send console commands directly to servers.
- **Queue Management** — Join and monitor the server queue.
- **List Servers** — View all servers accessible by the configured API key.
- **Help Command** — Displays all available commands.
- **Permission Control** — Admin-only commands.
- **Ephemeral Responses** — Sensitive info visible only to the invoking user.

> All logic and command implementations are in [`bot.py`](bot.py)

---

## ⚙️ Setup

### 1. Requirements

- Python 3.8+
- `discord.py`
- `requests`
- `python-dotenv`
- A Pterodactyl Panel instance with a valid **Client API Key**
- A Discord Bot Application and Token

---

### 2. Installation

Clone the repository:

```bash
git clone https://github.com/your-username/playhosting-pterodactyl-discord-bot.git
cd playhosting-pterodactyl-discord-bot
```

Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install dependencies:

```bash
pip install discord.py requests python-dotenv
```

> _Note: No `requirements.txt` provided; install manually._

---

### 3. Configuration

Create a `.env` file in the root directory with the following:

```env
DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN_HERE"
```

Replace the value with your actual bot token.

---

### 4. Running the Bot

To start the bot:

```bash
python bot.py
```

Upon startup, it will log in, sync slash commands, and print diagnostic output to the console.

---

## 💬 Discord Slash Commands

> All commands are namespaced under `/ptero`.

### 🔧 Configuration

| Command | Description |
|--------|-------------|
| `/ptero set_api <API_KEY>` | Set API key for the guild _(Admin only)_ |
| `/ptero set_url <PANEL_URL>` | Set Pterodactyl Panel URL _(Admin only)_ |
| `/ptero set_default <ID_or_alias>` | Set a default server _(Admin only)_ |
| `/ptero config` | View current config _(Admin only)_ |

---

### 🏷️ Server Alias Management

| Command | Description |
|--------|-------------|
| `/ptero set_alias <alias> <server_id>` | Create/update server alias _(Admin only)_ |
| `/ptero delete_alias <alias>` | Delete an alias _(Admin only)_ |
| `/ptero aliases` | List all aliases _(Admin only)_ |

---

### 📊 Server Info & Control

| Command | Description |
|--------|-------------|
| `/ptero list_servers` | List all accessible servers _(Admin only)_ |
| `/ptero status [server]` | Check server status _(Admin only)_ |
| `/ptero start [server]` | Start server _(Admin only)_ |
| `/ptero stop [server]` | Stop server _(Admin only)_ |
| `/ptero restart [server]` | Restart server _(Admin only)_ |
| `/ptero kill [server]` | Force stop server _(Admin only)_ |
| `/ptero command <command> [server]` | Send console command _(Admin only)_ |

---

### ⏳ Queue Management

| Command | Description |
|--------|-------------|
| `/ptero join_queue [server]` | Join the queue _(Admin only)_ |
| `/ptero queue_status [server]` | Check queue status _(Admin only)_ |

---

### ❓ Help

| Command | Description |
|--------|-------------|
| `/ptero help` | Show all available commands _(Admin only)_ |

---

## 🚨 Error Handling

The bot gracefully handles:

- Missing Discord bot token
- Missing admin permissions
- Invalid Pterodactyl configuration
- Pterodactyl API errors (e.g., not found, forbidden, conflict)
- API connection issues

---

## 🤝 Contributing

_This section can include how to contribute, open issues, or submit pull requests if made public._

---
