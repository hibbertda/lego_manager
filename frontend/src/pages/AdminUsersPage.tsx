import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, extractErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { AlertTriangle, CheckCircle2, Settings } from 'lucide-react';
import AdminTabs from '../components/AdminTabs';
import type { AdminUser } from '../types';

interface UsersResponse {
  users: AdminUser[];
  roles: string[];
}

export default function AdminUsersPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: async () => (await api.get<UsersResponse>('/admin/users')).data,
  });

  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('user');
  const [ssoUsername, setSsoUsername] = useState('');
  const [ssoRole, setSsoRole] = useState('user');

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ['admin-users'] });
  }

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await api.post('/admin/users', { username, password, role });
      setUsername('');
      setPassword('');
      setRole('user');
      setMessage('User created.');
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to create user.'));
    }
  }

  async function createPendingSso(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    try {
      const { data } = await api.post<{ message: string }>('/admin/users/pending-sso', {
        username: ssoUsername,
        role: ssoRole,
      });
      setSsoUsername('');
      setSsoRole('user');
      setMessage(data.message ?? 'Pre-authorized for SSO.');
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to pre-authorize user.'));
    }
  }

  async function updateRole(userId: number, newRole: string) {
    setError(null);
    try {
      await api.post(`/admin/users/${userId}/role`, { role: newRole });
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to update role.'));
    }
  }

  async function toggleActive(userId: number, isActive: boolean) {
    setError(null);
    try {
      await api.post(`/admin/users/${userId}/active`, { is_active: !isActive });
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to update account.'));
    }
  }

  async function deleteUser(userId: number) {
    setError(null);
    try {
      await api.delete(`/admin/users/${userId}`);
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to delete user.'));
    }
  }

  return (
    <div>
      <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Settings size={20} /> Admin — Users</h1>
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

      {isLoading ? (
        <span className="spinner" />
      ) : (
        <div className="card" style={{ padding: '1rem', marginBottom: '1.5rem', overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Auth</th>
                <th>Role</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data?.users.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>{u.email ?? '—'}</td>
                  <td>{u.auth_provider}</td>
                  <td>
                    <select value={u.role} onChange={(e) => updateRole(u.id, e.target.value)}>
                      {data.roles.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <span className={`badge ${u.is_active ? 'badge-success' : 'badge-secondary'}`}>
                      {u.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button className="btn btn-sm btn-outline" onClick={() => toggleActive(u.id, u.is_active)}>
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      {u.id !== session?.user?.id && (
                        <button className="btn btn-sm btn-danger-outline" onClick={() => deleteUser(u.id)}>
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
        <div className="card" style={{ padding: '1rem', flex: 1, minWidth: '20rem' }}>
          <h3>Create local user</h3>
          <form onSubmit={createUser}>
            <div className="field">
              <label>Username</label>
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div className="field">
              <label>Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <div className="field">
              <label>Role</label>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {(data?.roles ?? ['user', 'admin']).map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <button className="btn btn-primary" type="submit">
              Create user
            </button>
          </form>
        </div>

        <div className="card" style={{ padding: '1rem', flex: 1, minWidth: '20rem' }}>
          <h3>Pre-authorize SSO username</h3>
          <p className="muted" style={{ fontSize: '0.82rem' }}>
            Use this when automatic account creation is disabled for SSO.
          </p>
          <form onSubmit={createPendingSso}>
            <div className="field">
              <label>Username</label>
              <input type="text" value={ssoUsername} onChange={(e) => setSsoUsername(e.target.value)} required />
            </div>
            <div className="field">
              <label>Role</label>
              <select value={ssoRole} onChange={(e) => setSsoRole(e.target.value)}>
                {(data?.roles ?? ['user', 'admin']).map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <button className="btn btn-primary" type="submit">
              Pre-authorize
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
