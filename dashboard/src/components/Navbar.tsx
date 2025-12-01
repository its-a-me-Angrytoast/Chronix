import { useState, useEffect } from 'react';
import { Menu, X, Home, LayoutDashboard, BookOpen, Settings, LogIn, LogOut } from 'lucide-react';
import './Navbar.css';

interface NavbarProps {
  currentView: string;
  setView: (view: string) => void;
}

interface User {
  id: string;
  username: string;
  avatar: string | null;
  loggedIn: boolean;
}

const Navbar = ({ currentView, setView }: NavbarProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    fetch('/api/auth/me')
      .then(res => res.json())
      .then(data => {
        if (data.loggedIn) {
          setUser(data);
        }
      })
      .catch(err => console.error("Auth check failed", err));
  }, []);

  const handleLogin = () => {
    window.location.href = '/api/auth/login';
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
      setUser(null);
      window.location.reload();
    } catch (error) {
      console.error("Logout failed", error);
    }
  };

  const navItems = [
    { id: 'main', label: 'Main', icon: <Home size={20} /> },
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={20} /> },
    { id: 'docs', label: 'Docs', icon: <BookOpen size={20} /> },
    { id: 'settings', label: 'Settings', icon: <Settings size={20} /> },
  ];

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-logo" onClick={() => setView('main')}>
          CHRONIX
        </div>

        <div className="menu-icon" onClick={() => setIsOpen(!isOpen)}>
          {isOpen ? <X size={24} /> : <Menu size={24} />}
        </div>

        <div className={`nav-menu-wrapper ${isOpen ? 'active' : ''}`}>
           <ul className="nav-menu">
            {navItems.map((item) => (
              <li key={item.id} className="nav-item">
                <button
                  className={`nav-link ${currentView === item.id ? 'active' : ''}`}
                  onClick={() => {
                    setView(item.id);
                    setIsOpen(false);
                  }}
                  title={item.label} // Add tooltip for accessibility
                >
                  {item.icon}
                </button>
              </li>
            ))}
          </ul>

          <div className="nav-auth">
            {user ? (
              <div className="user-profile">
                {user.avatar ? (
                  <img 
                    src={`https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png`} 
                    alt={user.username} 
                    className="user-avatar"
                  />
                ) : (
                  <div className="user-avatar-placeholder">{user.username[0]}</div>
                )}
                <span className="user-name">{user.username}</span>
                <button className="btn-logout" onClick={handleLogout} title="Logout">
                  <LogOut size={18} />
                </button>
              </div>
            ) : (
              <button className="btn-login" onClick={handleLogin}>
                <LogIn size={18} />
                <span>Login with Discord</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;