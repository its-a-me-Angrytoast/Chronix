import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../utils/api';
import { toast } from 'react-hot-toast';

interface User {
  id: string;
  username: string;
  avatar: string | null;
  discriminator: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const data = await api<{ loggedIn: boolean } & User>('/api/auth/me');
        if (data.loggedIn) {
          setUser(data);
        } else {
          setUser(null);
        }
      } catch (error) {
        console.error('Auth check failed:', error);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  const login = () => {
    window.location.href = '/api/auth/login';
  };

  const logout = async () => {
    try {
      await api('/api/auth/logout', { method: 'POST' });
      setUser(null);
      toast.success('Logged out successfully');
      window.location.reload();
    } catch (error) {
      toast.error('Failed to logout');
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
