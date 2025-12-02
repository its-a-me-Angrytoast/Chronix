import { useState } from 'react';
import { Menu, X, Home, LayoutDashboard, BookOpen, Settings, LogIn, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Navbar.css';

interface NavbarProps {
  currentView: string;
  setView: (view: string) => void;
}

const Navbar = ({ currentView, setView }: NavbarProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const { user, login, logout } = useAuth();

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
                  title={item.label}
                >
                  {item.icon}
                  <span>{item.label}</span>
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
                <button className="btn-logout" onClick={logout} title="Logout">
                  <LogOut size={18} />
                </button>
              </div>
            ) : (
              <button className="btn-login" onClick={login}>
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