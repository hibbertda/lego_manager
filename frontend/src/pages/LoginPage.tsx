import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Blocks } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login, session } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      navigate('/sets');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid username or password.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>
          <Blocks size={24} style={{ verticalAlign: 'middle' }} /> LEGO Manager
        </h1>
        <p className="muted">Sign in to manage your collection.</p>

        {error && (
          <div className="alert alert-error">
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
            />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button className="btn btn-primary" type="submit" style={{ width: '100%' }} disabled={submitting}>
            {submitting ? <span className="spinner" /> : 'Log in'}
          </button>
        </form>

        {session?.oidc_enabled && (
          <div style={{ marginTop: '1rem', textAlign: 'center' }}>
            <a className="btn btn-outline" href="/login/oidc" style={{ width: '100%', justifyContent: 'center' }}>
              Sign in with {session.oidc_name ?? 'SSO'}
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
