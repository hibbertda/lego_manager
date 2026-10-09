import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertTriangle, Blocks } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function LoginPage({ fallback = false }: { fallback?: boolean }) {
  const { login, loginLocal, session } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(searchParams.get('error'));
  const [submitting, setSubmitting] = useState(false);

  // The fallback route (/login/local) always shows the local-login form and
  // bypasses local_disabled — a break-glass path for when SSO is enforced
  // but the external OIDC provider is unavailable.
  const localDisabled = !fallback && !!session?.local_disabled;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await (fallback ? loginLocal(username, password) : login(username, password));
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
        <p className="muted">
          {fallback ? 'Fallback sign-in (bypasses single sign-on).' : 'Sign in to manage your collection.'}
        </p>

        {error && (
          <div className="alert alert-error">
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        {localDisabled ? (
          <p className="muted">
            Local login is disabled. Use single sign-on, or the{' '}
            <a href="/login/local">fallback login</a> if needed.
          </p>
        ) : (
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
        )}

        {!fallback && session?.oidc_enabled && (
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
