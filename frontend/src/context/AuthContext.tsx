import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { api, extractErrorMessage, setCsrfToken } from '../api/client';
import type { SessionInfo } from '../types';

interface AuthContextValue {
  session: SessionInfo | null;
  loading: boolean;
  refresh: () => Promise<SessionInfo>;
  login: (username: string, password: string) => Promise<void>;
  loginLocal: (username: string, password: string) => Promise<void>;
  setup: (username: string, password: string, confirmPassword: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchSession(): Promise<SessionInfo> {
  const { data } = await api.get<SessionInfo>('/session');
  setCsrfToken(data.csrf_token);
  return data;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const data = await fetchSession();
    setSession(data);
    return data;
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const { data } = await api.post<SessionInfo>('/login', { username, password });
      setCsrfToken(data.csrf_token);
      setSession(data);
    } catch (err) {
      throw new Error(extractErrorMessage(err, 'Invalid username or password.'));
    }
  }, []);

  const loginLocal = useCallback(async (username: string, password: string) => {
    try {
      const { data } = await api.post<SessionInfo>('/login/local', { username, password });
      setCsrfToken(data.csrf_token);
      setSession(data);
    } catch (err) {
      throw new Error(extractErrorMessage(err, 'Invalid username or password.'));
    }
  }, []);

  const setup = useCallback(
    async (username: string, password: string, confirmPassword: string) => {
      try {
        const { data } = await api.post<SessionInfo>('/setup', {
          username,
          password,
          confirm_password: confirmPassword,
        });
        setCsrfToken(data.csrf_token);
        setSession(data);
      } catch (err) {
        throw new Error(extractErrorMessage(err, 'Could not create the admin account.'));
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    await api.post('/logout');
    await refresh();
  }, [refresh]);

  return (
    <AuthContext.Provider value={{ session, loading, refresh, login, loginLocal, setup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
