import { useState, useEffect, useRef } from 'react';
import { Coins, Swords, Music, Shield, Server, Activity, Zap, Terminal } from 'lucide-react';
import FeatureCard from '../components/FeatureCard';
import StatCard from '../components/StatCard';
import '../pages/Home.css';

interface HomeProps {
  setView: (view: string) => void;
}

interface DashboardStats {
  server_count: number;
  extensions: number;
  uptime: number | null;
  maintenance_mode?: boolean;
}

const Home = ({ setView }: HomeProps) => {
  const handleInvite = () => {
    const url = import.meta.env.VITE_DISCORD_INVITE_URL;
    if (url) {
      window.open(url, '_blank');
    } else {
      alert('Invite link not configured in .env');
    }
  };

  const [stats, setStats] = useState<DashboardStats>({
    server_count: 0,
    extensions: 0,
    uptime: null
  });

  // Store the calculated boot time timestamp
  const bootTimeRef = useRef<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch('/api/stats');
        if (res.ok) {
          const data = await res.json();
          setStats(data);
          
          if (data.uptime !== null) {
            // If we don't have a boot time yet, or if the new uptime is significantly different (e.g. bot restart), update it
            // We allow a 5-second drift before forcing a reset to account for network latency
            const estimatedBootTime = Date.now() - (data.uptime * 1000);
            
            if (bootTimeRef.current === null || Math.abs(bootTimeRef.current - estimatedBootTime) > 5000) {
               bootTimeRef.current = estimatedBootTime;
            }
          }
        }
      } catch (error) {
        console.error("Failed to fetch stats:", error);
      }
    };

    fetchStats();
    const pollInterval = setInterval(fetchStats, 5000);
    
    // Ticker updates based on local clock relative to boot time
    const tickInterval = setInterval(() => {
      if (bootTimeRef.current !== null) {
        const seconds = Math.floor((Date.now() - bootTimeRef.current) / 1000);
        setElapsedSeconds(seconds >= 0 ? seconds : 0);
      }
    }, 1000);

    return () => {
      clearInterval(pollInterval);
      clearInterval(tickInterval);
    };
  }, []);

  const formatUptime = (seconds: number | null) => {
    if (seconds === null) return "Offline";
    const d = Math.floor(seconds / (3600 * 24));
    const h = Math.floor((seconds % (3600 * 24)) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    
    if (d > 0) return `${d}d ${h}h ${m}m ${s}s`;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
  };

  return (
    <div className="home-page">
      {stats.maintenance_mode && (
        <div className="maintenance-banner">
          <Shield size={20} />
          <span>Maintenance Mode Active - Changes will not be saved</span>
        </div>
      )}

      <header className="hero-section">
        <div className="hero-content">
          <div className="logo-badge">CHRONIX v1.0</div>
          <h1>The Ultimate Discord Companion</h1>
          <p className="subtitle">
            Powerful economy, immersive RPG battles, high-quality music, and robust moderation. 
            All in one modular bot.
          </p>
          <div className="cta-buttons">
            <button className="btn-primary" onClick={handleInvite}>Add to Discord</button>
            <button className="btn-secondary" onClick={() => setView('docs')}>View Documentation</button>
          </div>
        </div>
      </header>

      {/* Live Stats Section moved here */}
      <section className="stats-section" style={{ marginBottom: '60px' }}>
        <StatCard 
          title="Servers" 
          value={stats.server_count} 
          icon={<Server size={32} color="#fff" />}
          color="#3b82f6" 
        />
        <StatCard 
          title="Uptime" 
          value={formatUptime(elapsedSeconds)} 
          icon={<Activity size={32} color="#fff" />}
          color="#10b981" 
        />
        <StatCard 
          title="Ping" 
          value="24ms" 
          icon={<Zap size={32} color="#fff" />}
          color="#f59e0b" 
        />
        <StatCard 
          title="Modules" 
          value={stats.extensions} 
          icon={<Terminal size={32} color="#fff" />}
          color="#8b5cf6" 
        />
      </section>

      <section className="features-section">
        <h2>Why Chronix?</h2>
        <div className="features-grid">
          <FeatureCard 
            title="Global Economy" 
            description="Complete banking system, marketplace, gambling, and interest rates."
            icon={<Coins size={40} color="currentColor" />}
          />
          <FeatureCard 
            title="RPG Gameplay" 
            description="Train pets, duel players, hunt monsters, and loot legendary weapons."
            icon={<Swords size={40} color="currentColor" />}
          />
          <FeatureCard 
            title="High-Fi Music" 
            description="Lag-free music streaming with Lavalink integration and queue management."
            icon={<Music size={40} color="currentColor" />}
          />
          <FeatureCard 
            title="Moderation" 
            description="Advanced tools to keep your server safe, including logs and auto-mod."
            icon={<Shield size={40} color="currentColor" />}
          />
        </div>
      </section>
    </div>
  );
};

export default Home;