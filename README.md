# Chronix — Modular Discord Bot

Chronix is an async-first, modular Discord bot built with `discord.py v2.x`. It focuses on a rich gameplay experience (economy, loot/crates, pets, weapons, battles), robust moderation utilities, high-quality music playback (Lavalink/Wavelink), and optional AI integrations. The project is developed in phases — consult the `Checklist` file for status on each feature.

This repository aims to be production-ready (typed, tested, DB-first) while still supporting a lightweight, file-backed development mode for local iteration.

## ✨ Key Features

### Core Bot
- **Gameplay**: Hunt, autohunt, crates, gems, pets, weapons, PvP/PvE battles.
- **Economy**: Global and per-guild balances, transactions, daily rewards.
- **Music**: Lavalink/Wavelink integration (optional).
- **AI**: Pluggable providers (Gemini/OpenAI) via an async client (opt-in).
- **Moderation**: Warnings, timed-mutes, logs.
- **Tickets & Announcements**: Panel-driven flows.

### 🌐 Dashboard (Web Interface)
- **Modern UI/UX**: Fully responsive and adaptive design, from 4K displays down to mobile.
- **Interactive Navigation**: Floating top bar with icon-only links and an animated dock at the bottom.
- **Dynamic Background**: Beautiful, animated canvas background (grid + particles).
- **Live Statistics**: Real-time uptime counter and bot stats directly on the main page.
- **Discord OAuth2 Login**: Securely connect your Discord account to view and manage your servers.
- **Server Management**:
    - View all Discord servers you are a member of.
    - Identify servers where Chronix is present.
    - Conditional "Manage" button for servers where you have permissions, leading to a cog management interface.
    - Conditional "Invite" button for servers where Chronix is not present.
- **Cog Configuration**: Toggle and manage various bot modules (cogs) per server (mocked functionality for now).
- **Persistent Settings**: User settings are saved locally in your browser.

## 🚀 Quickstart (Development)

### Bot Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/chronix.git # Replace with actual repo URL
    cd chronix
    ```
2.  **Copy example environment file:**
    ```bash
    cp .env.example .env
    ```
    Edit `.env` to set your `DISCORD_TOKEN`, `OWNER_ID`, and other bot-specific configurations.
3.  **Create and activate a virtual environment, then install Python dependencies:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
4.  **Run the bot:**
    ```bash
    python run.py
    ```

### Dashboard Setup (Frontend)

1.  **Navigate to the dashboard directory:**
    ```bash
    cd dashboard
    ```
2.  **Install Node.js dependencies:**
    ```bash
    npm install
    ```
3.  **Build the dashboard (required for `dashboard_server.py`):**
    ```bash
    npm run build
    ```
4.  **Configure Discord OAuth2 for Dashboard Login:**
    *   Go to the [Discord Developer Portal](https://discord.com/developers/applications) and select your application.
    *   Under the **OAuth2** tab, add `http://localhost:9091/api/auth/callback` to your **Redirects**.
    *   Copy your **Client ID** and **Client Secret**.
    *   **Edit your main `.env` file** (in the project root, not `dashboard/.env`):
        ```env
        # ... other bot settings ...

        # Dashboard OAuth2 Configuration
        DISCORD_CLIENT_ID=YOUR_DISCORD_CLIENT_ID
        DISCORD_CLIENT_SECRET=YOUR_DISCORD_CLIENT_SECRET
        DISCORD_REDIRECT_URI=http://localhost:9091/api/auth/callback
        SECRET_KEY=A_LONG_RANDOM_STRING_FOR_SESSION_COOKIES # IMPORTANT: Change this!

        # Dashboard "Add to Discord" Button Link
        VITE_DISCORD_INVITE_URL=https://discord.com/oauth2/authorize?client_id=YOUR_DISCORD_CLIENT_ID&permissions=8&scope=bot%20applications.commands
        ```
        Replace `YOUR_DISCORD_CLIENT_ID`, `YOUR_DISCORD_CLIENT_SECRET`, and `A_LONG_RANDOM_STRING_FOR_SESSION_COOKIES` with your actual values.

5.  **Start the standalone dashboard server (from project root):**
    ```bash
    python dashboard_server.py
    ```
    Access the dashboard at `http://localhost:9091`.

## 🐳 Docker (Development)

The included `docker-compose.yml` can bring up a Postgres database and Lavalink service. Example:

```bash
docker compose up --build
```

The `chronix` service builds the project image and mounts `./data` into the container for easy debugging and persistent file-backed state.

## 📝 Environment Variables

See `.env.example` for a comprehensive list of all configurable variables, including minimal requirements for running locally and advanced options for database, AI, and Lavalink integration.

## 🧪 Tests

Unit tests use `pytest` and `pytest-asyncio`. Run them from the repository root (inside a venv):

```bash
pytest -q
```

Note: the test suite includes deterministic tests for the battle engine, weapons, and AI client. Some tests require optional dependencies (see `requirements.txt`).

## 🤝 Contributing

- Follow the `Checklist` file to see planned features/phases.
- Keep changes small and include tests for new logic.

## 🗄️ Migrations

SQL migrations are in `migrations/`; apply them to your Postgres instance when ready. For quick testing you can use the bundled `docker-compose.yml` Postgres service and run:

```bash
docker compose exec postgres psql -U chronix -d chronix -f /path/to/migrations/0001_phase8.sql
```

## ⚠️ Troubleshooting

- If the bot fails to start due to missing DB: ensure `DATABASE_DSN` or `POSTGRES_*` are set and Postgres is reachable.
- If AI features are enabled, install `aiohttp` and set provider keys (Gemini/OpenAI).
- If dashboard login fails: Double-check `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, and `DISCORD_REDIRECT_URI` in your `.env` and the Discord Developer Portal. Ensure `SECRET_KEY` is set.
- If dashboard changes aren't visible: Remember to run `npm run build` from the `dashboard/` directory after any frontend code changes.

## 📄 License

This project is provided under the LICENSE in the repository root.