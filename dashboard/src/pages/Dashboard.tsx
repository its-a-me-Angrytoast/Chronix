import { useState, useEffect } from 'react';
import { Shield, ExternalLink, Settings, Loader2, ArrowLeft, Box, Music, Coins, MessageSquare, UserPlus, Bot, ScrollText, Clock, Wrench } from 'lucide-react';
import { api } from '../utils/api';
import './Dashboard.css';

interface Guild {
  id: string;
  name: string;
  icon: string | null;
  permissions: string;
  hasBot?: boolean;
  canManage?: boolean;
}

const Dashboard = () => {
  const [guilds, setGuilds] = useState<Guild[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedGuild, setSelectedGuild] = useState<Guild | null>(null);

  // Mock Cogs Data
  const COGS = [
    { id: 'economy', name: 'Economy', description: 'Bank, shop, gambling system', icon: <Coins size={24} />, enabled: true },
    { id: 'music', name: 'Music', description: 'High quality music playback', icon: <Music size={24} />, enabled: true },
    { id: 'moderation', name: 'Moderation', description: 'Kick, ban, mute, warn', icon: <Shield size={24} />, enabled: true },
    { id: 'logs', name: 'Logging', description: 'Track server events', icon: <ScrollText size={24} />, enabled: false },
    { id: 'welcomer', name: 'Welcomer', description: 'Welcome new members', icon: <UserPlus size={24} />, enabled: true },
    { id: 'ai', name: 'AI Chat', description: 'AI-powered chat bot', icon: <Bot size={24} />, enabled: false },
    { id: 'tickets', name: 'Tickets', description: 'Support ticket system', icon: <MessageSquare size={24} />, enabled: false },
    { id: 'tempvc', name: 'Temp VC', description: 'Temporary voice channels', icon: <Clock size={24} />, enabled: true },
    { id: 'leveling', name: 'Leveling', description: 'XP and leveling system', icon: <Box size={24} />, enabled: true },
    { id: 'utils', name: 'Utilities', description: 'Server utility commands', icon: <Wrench size={24} />, enabled: true },
  ];

  useEffect(() => {
    const fetchGuilds = async () => {
      try {
        const data = await api<any[]>('/api/user/guilds');
        
        const processed = data.map((g: any) => {
          const perms = BigInt(g.permissions);
          const canManage = (perms & BigInt(0x20)) === BigInt(0x20) || (perms & BigInt(0x8)) === BigInt(0x8);
          
          return {
            ...g,
            hasBot: false, 
            canManage: canManage
          };
        });
        
        setGuilds(processed);
      } catch (err: any) {
        console.error(err);
        if (err.status === 401) {
             setError('Please login to view your servers.');
        } else {
             setError('Failed to load servers.');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchGuilds();
  }, []);

  const handleInvite = (guildId: string) => {
    const baseUrl = import.meta.env.VITE_DISCORD_INVITE_URL || 'https://discord.com/oauth2/authorize?client_id=YOUR_ID&permissions=8&scope=bot%20applications.commands';
    window.open(`${baseUrl}&guild_id=${guildId}`, '_blank');
  };

  const handleManage = (guild: Guild) => {
    setSelectedGuild(guild);
  };

  const toggleCog = (cogId: string) => {
    // Mock toggle functionality
    console.log(`Toggling cog ${cogId} for guild ${selectedGuild?.id}`);
    // In a real app, this would send an API request
  };

  if (loading) {
    return (
      <div className="dashboard-page loading">
        <Loader2 className="animate-spin" size={48} color="var(--accent)" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-page error">
        <h2>{error}</h2>
        {error.includes('login') && (
           <button className="btn-primary" onClick={() => window.location.href = '/api/auth/login'}>
             Login with Discord
           </button>
        )}
      </div>
    );
  }

  // Render Guild Management View
  if (selectedGuild) {
    return (
      <div className="dashboard-page manage-view">
        <header className="dashboard-header">
          <button className="back-btn" onClick={() => setSelectedGuild(null)}>
            <ArrowLeft size={20} />
            Back to Servers
          </button>
          <div className="selected-guild-info">
             {selectedGuild.icon ? (
                <img src={`https://cdn.discordapp.com/icons/${selectedGuild.id}/${selectedGuild.icon}.png`} alt={selectedGuild.name} className="header-icon" />
              ) : (
                <div className="header-icon-placeholder">
                  {selectedGuild.name.substring(0, 2).toUpperCase()}
                </div>
              )}
            <h1>{selectedGuild.name}</h1>
          </div>
          <p>Manage modules and settings for this server.</p>
        </header>

        <div className="cogs-grid">
          {COGS.map(cog => (
            <div key={cog.id} className={`cog-card ${cog.enabled ? 'enabled' : 'disabled'}`}>
              <div className="cog-icon-wrapper">
                {cog.icon}
              </div>
              <div className="cog-info">
                <h3>{cog.name}</h3>
                <p>{cog.description}</p>
              </div>
              <div className="cog-action">
                <label className="toggle-switch">
                  <input 
                    type="checkbox" 
                    checked={cog.enabled} 
                    onChange={() => toggleCog(cog.id)} 
                  />
                  <span className="slider round"></span>
                </label>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Render Server List View
  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <h1>Dashboard</h1>
        <p>Select a server to manage Chronix.</p>
      </header>

      <div className="servers-grid">
        {guilds.map(guild => (
          <div 
            key={guild.id} 
            className={`guild-card ${!guild.hasBot ? 'no-bot' : ''}`}
          >
            <div className="guild-icon">
              {guild.icon ? (
                <img src={`https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`} alt={guild.name} />
              ) : (
                <div className="guild-icon-placeholder">
                  {guild.name.substring(0, 2).toUpperCase()}
                </div>
              )}
              {guild.hasBot && (
                <div className="bot-badge" title="Chronix is here">
                  <Shield size={12} />
                </div>
              )}
            </div>

            <div className="guild-info">
              <h3>{guild.name}</h3>
              <p>{guild.canManage ? 'Admin / Manager' : 'Member'}</p>
            </div>

            <div className="guild-actions">
              {/* Logic simplified for standalone demo: always show Manage if canManage, assuming bot is there or we want to config anyway */}
              {guild.canManage ? (
                  <button 
                    className="action-btn manage"
                    onClick={() => handleManage(guild)}
                  >
                    <Settings size={16} />
                    Manage
                  </button>
              ) : (
                  <span className="status-text">Member</span>
              )}
              
              {!guild.hasBot && guild.canManage && (
                 <button 
                    className="action-btn invite"
                    onClick={() => handleInvite(guild.id)}
                    style={{ marginLeft: '8px' }}
                  >
                    <ExternalLink size={16} />
                  </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Dashboard;