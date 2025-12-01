import './Docs.css';

const Docs = () => {
  return (
    <div className="docs-page">
      <aside className="docs-sidebar">
        <h3>Documentation</h3>
        <ul>
          <li><a href="#intro">Introduction</a></li>
          <li><a href="#features">Features</a></li>
          <li><a href="#quickstart">Quickstart</a></li>
          <li><a href="#config">Configuration</a></li>
        </ul>
      </aside>

      <main className="docs-content">
        <section id="intro">
          <h1>Chronix Documentation</h1>
          <p>
            Chronix is an async-first, modular Discord bot built with discord.py v2.x. 
            It is designed to be the ultimate companion for your Discord server, offering 
            features ranging from economy to moderation.
          </p>
        </section>

        <section id="features">
          <h2>Key Features</h2>
          <ul>
            <li><strong>Gameplay:</strong> Hunt, autohunt, crates, gems, pets, weapons, PvP/PvE battles.</li>
            <li><strong>Economy:</strong> Global and per-guild balances, transactions, daily rewards.</li>
            <li><strong>Music:</strong> Lavalink/Wavelink integration for high-quality audio.</li>
            <li><strong>Moderation:</strong> Warnings, timed-mutes, logs, and tickets.</li>
            <li><strong>AI:</strong> Optional integration with Gemini/OpenAI.</li>
          </ul>
        </section>

        <section id="quickstart">
          <h2>Quickstart (Development)</h2>
          <p>To get started with development:</p>
          <pre>
{`# 1. Clone and setup env
cp .env.example .env

# 2. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Run the bot
python run.py`}
          </pre>
        </section>

        <section id="config">
          <h2>Configuration</h2>
          <p>
            Chronix is configured via environment variables. See <code>.env.example</code> for all options.
            Key variables include:
          </p>
          <ul>
            <li><code>DISCORD_TOKEN</code>: Your bot token.</li>
            <li><code>OWNER_ID</code>: Your Discord User ID.</li>
            <li><code>DATABASE_DSN</code>: Connection string for PostgreSQL (optional for dev).</li>
          </ul>
        </section>
      </main>
    </div>
  );
};

export default Docs;
