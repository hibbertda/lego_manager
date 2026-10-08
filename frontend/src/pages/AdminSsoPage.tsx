import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, extractErrorMessage } from '../api/client';
import { AlertTriangle, CheckCircle2, Settings } from 'lucide-react';
import AdminTabs from '../components/AdminTabs';
import type { OidcProvider } from '../types';

interface SsoResponse {
  provider: OidcProvider | null;
  roles: string[];
}

export default function AdminSsoPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-sso'],
    queryFn: async () => (await api.get<SsoResponse>('/admin/sso')).data,
  });

  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: 'OIDC Provider',
    issuer: '',
    client_id: '',
    client_secret: '',
    scopes: 'openid profile email',
    default_role: 'user',
    enabled: false,
    disable_local_login: false,
    auto_create_users: true,
  });

  useEffect(() => {
    if (data?.provider) {
      setForm({
        name: data.provider.name,
        issuer: data.provider.issuer,
        client_id: data.provider.client_id,
        client_secret: '',
        scopes: data.provider.scopes,
        default_role: data.provider.default_role,
        enabled: data.provider.enabled,
        disable_local_login: data.provider.disable_local_login,
        auto_create_users: data.provider.auto_create_users,
      });
    }
  }, [data]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await api.post('/admin/sso', form);
      setMessage('SSO configuration saved.');
      refetch();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to save SSO configuration.'));
    }
  }

  if (isLoading) return <span className="spinner" />;

  return (
    <div>
      <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Settings size={20} /> Admin — Single Sign-On</h1>
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

      <div className="card" style={{ padding: '1.25rem', maxWidth: '36rem' }}>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Display name</label>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="field">
            <label>Issuer URL</label>
            <input type="text" value={form.issuer} onChange={(e) => setForm({ ...form, issuer: e.target.value })} />
          </div>
          <div className="field">
            <label>Client ID</label>
            <input
              type="text"
              value={form.client_id}
              onChange={(e) => setForm({ ...form, client_id: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Client secret</label>
            <input
              type="password"
              placeholder={data?.provider ? '(unchanged — leave blank to keep)' : ''}
              value={form.client_secret}
              onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Scopes</label>
            <input type="text" value={form.scopes} onChange={(e) => setForm({ ...form, scopes: e.target.value })} />
          </div>
          <div className="field">
            <label>Default role for new SSO users</label>
            <select value={form.default_role} onChange={(e) => setForm({ ...form, default_role: e.target.value })}>
              {(data?.roles ?? ['user', 'admin']).map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.6rem' }}>
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            Enable SSO
          </label>
          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.6rem' }}>
            <input
              type="checkbox"
              checked={form.auto_create_users}
              onChange={(e) => setForm({ ...form, auto_create_users: e.target.checked })}
            />
            Automatically create accounts for new SSO identities
          </label>
          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '1rem' }}>
            <input
              type="checkbox"
              checked={form.disable_local_login}
              onChange={(e) => setForm({ ...form, disable_local_login: e.target.checked })}
            />
            Disable local username/password login
          </label>
          <button className="btn btn-primary" type="submit">
            Save SSO configuration
          </button>
        </form>
      </div>
    </div>
  );
}
