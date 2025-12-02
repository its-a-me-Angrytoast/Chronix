import { useState, useEffect } from 'react';
import { Shield, Bell, Moon, Globe, Volume2, Save } from 'lucide-react';
import { toast } from 'react-hot-toast';
import './Settings.css';

interface SettingsState {
  notifications: boolean;
  darkMode: boolean;
  language: string;
  volume: number;
  autoMod: boolean;
  [key: string]: any; // Allow indexing
}

const Settings = () => {
  const [settings, setSettings] = useState<SettingsState>(() => {
    const saved = localStorage.getItem('chronix_settings');
    return saved ? JSON.parse(saved) : {
      notifications: true,
      darkMode: true,
      language: 'English',
      volume: 80,
      autoMod: true
    };
  });

  useEffect(() => {
    localStorage.setItem('chronix_settings', JSON.stringify(settings));
  }, [settings]);

  const handleChange = (key: string, value: any) => {
    setSettings((prev: SettingsState) => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    // Settings are auto-saved via useEffect, but we can show a confirmation
    toast.success('Settings saved to local storage!');
  };

  return (
    <div className="settings-page">
      <header className="settings-header">
        <h1>Settings</h1>
        <p>Manage your dashboard preferences and bot configurations.</p>
      </header>

      <div className="settings-grid">
        {/* Appearance Section */}
        <section className="settings-card">
          <div className="card-header">
            <Moon size={24} />
            <h2>Appearance</h2>
          </div>
          <div className="setting-item">
            <label>Dark Mode</label>
            <div className="toggle-switch" onClick={() => handleChange('darkMode', !settings.darkMode)}>
              <div className={`switch ${settings.darkMode ? 'on' : 'off'}`} />
            </div>
          </div>
        </section>

        {/* Notifications Section */}
        <section className="settings-card">
          <div className="card-header">
            <Bell size={24} />
            <h2>Notifications</h2>
          </div>
          <div className="setting-item">
            <label>Enable Notifications</label>
            <div className="toggle-switch" onClick={() => handleChange('notifications', !settings.notifications)}>
              <div className={`switch ${settings.notifications ? 'on' : 'off'}`} />
            </div>
          </div>
        </section>

        {/* Language Section */}
        <section className="settings-card">
          <div className="card-header">
            <Globe size={24} />
            <h2>Language</h2>
          </div>
          <div className="setting-item">
            <label>Dashboard Language</label>
            <select 
              value={settings.language} 
              onChange={(e) => handleChange('language', e.target.value)}
              className="settings-select"
            >
              <option>English</option>
              <option>Spanish</option>
              <option>French</option>
              <option>German</option>
            </select>
          </div>
        </section>

        {/* Audio Section */}
        <section className="settings-card">
          <div className="card-header">
            <Volume2 size={24} />
            <h2>Audio</h2>
          </div>
          <div className="setting-item">
            <label>Default Volume: {settings.volume}%</label>
            <input 
              type="range" 
              min="0" 
              max="100" 
              value={settings.volume} 
              onChange={(e) => handleChange('volume', parseInt(e.target.value))}
              className="settings-slider"
            />
          </div>
        </section>

        {/* Moderation Section */}
        <section className="settings-card">
          <div className="card-header">
            <Shield size={24} />
            <h2>Auto-Moderation</h2>
          </div>
          <div className="setting-item">
            <label>Active Protection</label>
            <div className="toggle-switch" onClick={() => handleChange('autoMod', !settings.autoMod)}>
              <div className={`switch ${settings.autoMod ? 'on' : 'off'}`} />
            </div>
          </div>
        </section>
      </div>

      <div className="save-section">
        <button className="btn-primary save-btn" onClick={handleSave}>
          <Save size={18} />
          Save Changes
        </button>
      </div>
    </div>
  );
};

export default Settings;
