import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import api from '../services/api';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  /**
   * Attempt to restore the session by calling /users/me/.
   * If the HttpOnly access cookie is still valid the backend returns the
   * current user; if not, the response interceptor in api.js tries a silent
   * refresh before giving up.
   */
  const restoreSession = useCallback(async () => {
    try {
      const resp = await api.get('/users/me/');
      setUser(resp.data);
    } catch {
      // No valid session — user stays null
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  /**
   * POST credentials → backend sets HttpOnly access + refresh cookies.
   * We receive only the user payload (no tokens exposed to JS).
   */
  const login = async (username, password) => {
    try {
      const response = await api.post('/users/login/', { username, password });
      setUser(response.data.user);
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.error || 'Login failed',
      };
    }
  };

  /**
   * Register a new account.  Does NOT auto-login; the caller should redirect
   * to /login so the user explicitly signs in.
   */
  const register = async (userData) => {
    try {
      await api.post('/users/', userData);
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data || 'Registration failed',
      };
    }
  };

  /**
   * POST to /users/logout/ — the backend blacklists the refresh token and
   * clears both HttpOnly cookies via Set-Cookie headers.
   */
  const logout = async () => {
    try {
      await api.post('/users/logout/');
    } catch {
      // Even if the request fails, clear local state so the UI resets
    } finally {
      setUser(null);
    }
  };

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    refreshUser: restoreSession,  // expose so components can force a re-fetch
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
