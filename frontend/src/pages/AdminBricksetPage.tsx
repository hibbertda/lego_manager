import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, extractErrorMessage } from '../api/client';
import { AlertTriangle, CheckCircle2, Settings } from 'lucide-react';
import AdminTabs from '../components/AdminTabs';
import type { BricksetSettings } from '../types';

interface BricksetResponse {
  settings: BricksetSettings | null;
  env_api_key_set: boolean;
}

export default function AdminBricksetPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-brickset'],
    queryFn: async () => (await api.get<BricksetResponse>('/admin/brickset')).data,
  });

  const [apiKey, setApiKey] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (data?.settings) {
      setUsername(data.settings.username ?? '');
    }
  }, [data]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await api.post('/admin/brickset', { api_key: apiKey, username, password });
      setApiKey('');
      setPassword('');
      setMessage('Brickset API settings saved.');
      refetch();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to save Brickset settings.'));
    }
  }

  if (isLoading) return <span className="spinner" />;

  return (
    <div>
      <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Settings size={20} /> Admin — Brickset API</h1>
      <AdminTabs />

      {error && (
        <div className="alert alert-error">
          <AlertTriangle size={15} /> {error}
        </div>
      )}
      {message && (
        <div className="alert alert-success">
          <CheckCircle2 size={15} /> {message}
        </div>
      )}

      {data?.env_api_key_set && !data.settings?.api_key && (
        <div className="alert alert-success">An API key is configured via environment variable.</div>
      )}

      <div className="card" style={{ padding: '1.25rem', maxWidth: '32rem' }}>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>API key</label>
            <input
              type="password"
              placeholder={data?.settings?.api_key ? '(unchanged — leave blank to keep)' : ''}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
          <div className="field">
            <label>Brickset username</label>
            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="field">
            <label>Brickset password</label>
            <input
              type="password"
              placeholder={data?.settings?.password ? '(unchanged — leave blank to keep)' : ''}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button className="btn btn-primary" type="submit">
            Save Brickset settings
          </button>
        </form>
      </div>
    </div>
  );
}
