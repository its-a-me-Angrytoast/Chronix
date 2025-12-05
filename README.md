# Chronix Bot

A robust, modular Discord bot built with `discord.py`, featuring a Cog-based architecture for easy scalability.

## Features

- **Modular Architecture**: Uses Cogs to organize code into logical extensions (General, Moderation, etc.).
- **Moderation Tools**: Kick, Ban, and Clear messages with permission checks.
- **General Utilities**: Ping latency check, Info command.
- **Application Commands**: Support for Slash Commands via `!sync`.
- **Configurable**: Easy configuration via environment variables.

## Prerequisites

- Python 3.8 or higher
- A Discord Bot Token (from the [Discord Developer Portal](https://discord.com/developers/applications))

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/chronix.git
   cd chronix
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   - Copy the example environment file:
     ```bash
     cp .env.example .env
     ```
   - Open `.env` and fill in your details:
     ```env
     DISCORD_TOKEN=your_actual_discord_token
     BOT_OWNER_ID=your_discord_user_id_integer
     BOT_NAME="Chronix Bot"
     ```

## Usage

Run the bot:
```bash
python main.py
```

### Commands

*   `!ping` - Check bot latency.
*   `!info` - Display bot information.
*   `!kick <member> [reason]` - Kick a user (requires Kick Members permission).
*   `!ban <member> [reason]` - Ban a user (requires Ban Members permission).
*   `!clear <amount>` - Delete messages (requires Manage Messages permission).
*   `!sync` - Sync slash commands (Owner only).

## Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.
