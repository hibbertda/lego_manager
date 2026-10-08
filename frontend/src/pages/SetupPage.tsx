import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Blocks } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function SetupPage() {
  const { setup, session, loading } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && session && !session.needs_setup) {
    navigate(session.authenticated ? '/sets' : '/login', { replace: true });
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await setup(username, password, confirm);
      navigate('/sets');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the admin account.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>
          <Blocks size={24} style={{ verticalAlign: 'middle' }} /> Welcome
        </h1>
        <p className="muted">Create the initial admin account to get started.</p>

        {error && (
          <div className="alert alert-error">
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Username</label>
            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <div className="field">
            <label>Confirm password</label>
            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
          </div>
          <button className="btn btn-primary" type="submit" style={{ width: '100%' }} disabled={submitting}>
            {submitting ? <span className="spinner" /> : 'Create admin account'}
          </button>
        </form>
      </div>
    </div>
  );
}
