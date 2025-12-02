import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster } from 'react-hot-toast';
import './App.css';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import Docs from './pages/Docs';
import Settings from './pages/Settings';
import Dock from './components/Dock';
import Aurora from './components/Aurora';
import { AuthProvider } from './context/AuthContext';
import { VscHome, VscDashboard, VscBook, VscSettingsGear } from 'react-icons/vsc';

function AppContent() {
  const [currentView, setView] = useState('main');

  const dockItems = [
    { icon: <VscHome size={18} />, label: 'Main', onClick: () => setView('main') },
    { icon: <VscDashboard size={18} />, label: 'Dashboard', onClick: () => setView('dashboard') },
    { icon: <VscBook size={18} />, label: 'Docs', onClick: () => setView('docs') },
    { icon: <VscSettingsGear size={18} />, label: 'Settings', onClick: () => setView('settings') },
  ];

  return (
    <div className="app-layout">
      <Aurora />
      <Navbar currentView={currentView} setView={setView} />
      
      <div className="content-container">
        <main className="main-content">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentView}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              style={{ width: '100%' }}
            >
              {currentView === 'main' && <Home setView={setView} />}
              {currentView === 'dashboard' && <Dashboard />}
              {currentView === 'docs' && <Docs />}
              {currentView === 'settings' && <Settings />}
            </motion.div>
          </AnimatePresence>
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
      <Toaster 
        position="top-right"
        toastOptions={{
          style: {
            background: '#1e293b',
            color: '#fff',
            border: '1px solid #334155',
          },
        }}
      />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
