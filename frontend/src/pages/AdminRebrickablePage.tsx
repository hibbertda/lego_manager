import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, extractErrorMessage } from '../api/client';
import { AlertTriangle, CheckCircle2, Settings } from 'lucide-react';
import AdminTabs from '../components/AdminTabs';
import type { RebrickableSettings } from '../types';

interface RebrickableResponse {
  settings: RebrickableSettings | null;
  env_api_key_set: boolean;
}

export default function AdminRebrickablePage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-rebrickable'],
    queryFn: async () => (await api.get<RebrickableResponse>('/admin/rebrickable')).data,
  });

  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await api.post('/admin/rebrickable', { api_key: apiKey });
      setApiKey('');
      setMessage('Rebrickable API settings saved.');
      refetch();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to save Rebrickable settings.'));
    }
  }

  if (isLoading) return <span className="spinner" />;

  return (
    <div>
      <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Settings size={20} /> Admin — Rebrickable API</h1>
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

      <p className="muted" style={{ maxWidth: '32rem' }}>
        Used to fetch each set&apos;s part list and minifigs (image, quantity) on the set detail page.
        Brickset doesn&apos;t provide this data, so a separate free API key from{' '}
        <a href="https://rebrickable.com/api/" target="_blank" rel="noreferrer">rebrickable.com</a> is required.
      </p>

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
          <button className="btn btn-primary" type="submit">
            Save Rebrickable settings
          </button>
        </form>
      </div>
    </div>
  );
}
