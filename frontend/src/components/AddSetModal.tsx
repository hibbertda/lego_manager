import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Pencil, Plus, Search, X } from 'lucide-react';
import { api, extractErrorMessage } from '../api/client';
import { ALL_BUILD_STATUSES, BUILD_STATUS_META } from '../constants';
import { useAuth } from '../context/AuthContext';

export default function AddSetModal({ onClose }: { onClose: () => void }) {
  const { session, refresh } = useAuth();
  const navigate = useNavigate();
  const [method, setMethod] = useState<'auto' | 'manual'>('auto');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [setNumber, setSetNumber] = useState('');
  const [autoStatus, setAutoStatus] = useState('not_started');

  const [mSetNumber, setMSetNumber] = useState('');
  const [mName, setMName] = useState('');
  const [mYear, setMYear] = useState('');
  const [mPieces, setMPieces] = useState('');
  const [mTheme, setMTheme] = useState('');
  const [mStatus, setMStatus] = useState('not_started');
  const [mImage, setMImage] = useState<File | null>(null);
  const [mInstructions, setMInstructions] = useState<FileList | null>(null);

  async function submitAuto(e: React.FormEvent) {
    e.preventDefault();
    if (!setNumber.trim()) {
      setError('Set number is required.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('set_number', setNumber.trim());
      form.append('build_status', autoStatus);
      await api.post('/sets', form);
      await refresh();
      onClose();
      navigate('/sets');
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to retrieve set data from Brickset.'));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitManual(e: React.FormEvent) {
    e.preventDefault();
    if (!mSetNumber.trim() || !mName.trim()) {
      setError('Set number and name are required.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('set_number', mSetNumber.trim());
      form.append('name', mName.trim());
      if (mYear) form.append('year', mYear);
      if (mPieces) form.append('pieces', mPieces);
      if (mTheme) form.append('theme', mTheme);
      form.append('build_status', mStatus);
      if (mImage) form.append('image', mImage);
      if (mInstructions) {
        Array.from(mInstructions).forEach((f) => form.append('instructions', f));
      }
      const { data } = await api.post<{ set_id: number }>('/sets/manual', form);
      await refresh();
      onClose();
      navigate(`/sets/${data.set_id}`);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to add the set.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Plus size={18} /> Add a Set
          </h3>
          <button className="modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="method-toggle">
          <button className={method === 'auto' ? 'active' : ''} onClick={() => setMethod('auto')}>
            <Search size={14} /> Automatic — Brickset
          </button>
          <button className={method === 'manual' ? 'active' : ''} onClick={() => setMethod('manual')}>
            <Pencil size={14} /> Add Manually
          </button>
        </div>

        {error && (
          <div className="alert alert-error">
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        {method === 'auto' ? (
          <form onSubmit={submitAuto}>
            {!session?.brickset_configured && (
              <div className="alert alert-error">
                Brickset API key is not configured.{' '}
                {session?.user?.is_admin ? (
                  <a href="#" onClick={(e) => { e.preventDefault(); onClose(); navigate('/admin/brickset'); }}>
                    Set it up here
                  </a>
                ) : (
                  'Ask an administrator to configure it, or use Manual instead.'
                )}
              </div>
            )}
            <div className="field">
              <label>Set Number</label>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                placeholder="e.g. 75192"
                value={setNumber}
                onChange={(e) => setSetNumber(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label>Category</label>
              <select value={autoStatus} onChange={(e) => setAutoStatus(e.target.value)}>
                {ALL_BUILD_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {BUILD_STATUS_META[s].label}
                  </option>
                ))}
              </select>
            </div>
            <button className="btn btn-primary" type="submit" disabled={submitting}>
              {submitting ? <span className="spinner" /> : 'Fetch from Brickset'}
            </button>
          </form>
        ) : (
          <form onSubmit={submitManual}>
            <div className="field">
              <label>Set Number *</label>
              <input
                type="tel"
                placeholder="e.g. 75192-1"
                value={mSetNumber}
                onChange={(e) => setMSetNumber(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label>Name *</label>
              <input type="text" value={mName} onChange={(e) => setMName(e.target.value)} required />
            </div>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <div className="field" style={{ flex: 1 }}>
                <label>Year</label>
                <input type="number" value={mYear} onChange={(e) => setMYear(e.target.value)} />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label>Pieces</label>
                <input type="number" value={mPieces} onChange={(e) => setMPieces(e.target.value)} />
              </div>
            </div>
            <div className="field">
              <label>Theme</label>
              <input type="text" value={mTheme} onChange={(e) => setMTheme(e.target.value)} />
            </div>
            <div className="field">
              <label>Category</label>
              <select value={mStatus} onChange={(e) => setMStatus(e.target.value)}>
                {ALL_BUILD_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {BUILD_STATUS_META[s].label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Cover image</label>
              <input type="file" accept="image/*" onChange={(e) => setMImage(e.target.files?.[0] ?? null)} />
            </div>
            <div className="field">
              <label>Instruction PDFs</label>
              <input
                type="file"
                accept="application/pdf"
                multiple
                onChange={(e) => setMInstructions(e.target.files)}
              />
            </div>
            <button className="btn btn-primary" type="submit" disabled={submitting}>
              {submitting ? <span className="spinner" /> : 'Add set manually'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
