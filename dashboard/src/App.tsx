import { useState } from 'react';
import './App.css';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import Docs from './pages/Docs';
import Settings from './pages/Settings';
import Dock from './components/Dock';
import Aurora from './components/Aurora';
import { VscHome, VscDashboard, VscBook, VscSettingsGear } from 'react-icons/vsc';


function App() {
  const [currentView, setView] = useState('main');

  const renderView = () => {
    switch (currentView) {
      case 'main':
        return <Home setView={setView} />;
      case 'dashboard':
        return <Dashboard />;
      case 'docs':
        return <Docs />;
      case 'settings':
        return <Settings />;
      default:
        return <Home setView={setView} />;
    }
  };

  const dockItems = [
    { icon: <VscHome size={18} />, label: 'Main', onClick: () => setView('main') },
    { icon: <VscDashboard size={18} />, label: 'Dashboard', onClick: () => setView('dashboard') },
    { icon: <VscBook size={18} />, label: 'Docs', onClick: () => setView('docs') },
    { icon: <VscSettingsGear size={18} />, label: 'Settings', onClick: () => setView('settings') },
  ];


  return (
    <div className="app-layout">
      <Aurora /> {/* Aurora component as background */}
      <Navbar currentView={currentView} setView={setView} />
      
      <div className="content-container">
        <main className="main-content">
          {renderView()}
        </main>

        <footer className="footer">
          <p>&copy; {new Date().getFullYear()} Chronix Bot Project. Open Source.</p>
        </footer>
      </div>

      <Dock 
        items={dockItems}
        panelHeight={68}
        baseItemSize={50}
      />
    </div>
  );
}

export default App;