import { Suspense, lazy, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, extractErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { BUILD_STATUS_META, OWNED_BUILD_STATUSES } from '../constants';
import type { SetDetailResponse } from '../types';

const PdfViewer = lazy(() => import('../components/PdfViewer'));

export default function SetDetailPage() {
  const { setId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { session } = useAuth();
  const isAdmin = !!session?.user?.is_admin;

  const { data, isLoading, error } = useQuery({
    queryKey: ['set-detail', setId],
    queryFn: async () => {
      const { data } = await api.get<SetDetailResponse>(`/sets/${setId}`);
      return data;
    },
  });

  const [buildStatus, setBuildStatus] = useState('');
  const [buildPage, setBuildPage] = useState('');
  const [location, setLocation] = useState('');
  const [savingProgress, setSavingProgress] = useState(false);
  const [savingLocation, setSavingLocation] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const set = data?.set;

  // Sync local form state once the set loads (only on first load / id change).
  if (set && buildStatus === '' && buildPage === '') {
    setBuildStatus(set.build_status);
    setBuildPage(String(set.build_page ?? 0));
    setLocation(set.location ?? '');
  }

  async function saveProgress(e: React.FormEvent) {
    e.preventDefault();
    setSavingProgress(true);
    setActionError(null);
    try {
      await api.post(`/sets/${setId}/progress`, {
        build_status: buildStatus,
        build_page: parseInt(buildPage, 10) || 0,
      });
      queryClient.invalidateQueries({ queryKey: ['set-detail', setId] });
      queryClient.invalidateQueries({ queryKey: ['sets-list'] });
      setActionMessage('Progress saved.');
    } catch (err) {
      setActionError(extractErrorMessage(err, 'Failed to save progress.'));
    } finally {
      setSavingProgress(false);
    }
  }

  async function saveLocation(e: React.FormEvent) {
    e.preventDefault();
    setSavingLocation(true);
    setActionError(null);
    try {
      await api.post(`/sets/${setId}/location`, { location });
      queryClient.invalidateQueries({ queryKey: ['set-detail', setId] });
      setActionMessage('Location updated.');
    } catch (err) {
      setActionError(extractErrorMessage(err, 'Failed to update location.'));
    } finally {
      setSavingLocation(false);
    }
  }

  async function refreshFromBrickset() {
    setActionError(null);
    try {
      await api.post(`/sets/${setId}/refresh`);
      queryClient.invalidateQueries({ queryKey: ['set-detail', setId] });
      setActionMessage('Set refreshed from Brickset.');
    } catch (err) {
      setActionError(extractErrorMessage(err, 'Failed to refresh from Brickset.'));
    }
  }

  async function deleteSet() {
    try {
      await api.delete(`/sets/${setId}`);
      queryClient.invalidateQueries({ queryKey: ['sets-list'] });
      navigate('/sets');
    } catch (err) {
      setActionError(extractErrorMessage(err, 'Failed to delete set.'));
      setShowDeleteConfirm(false);
    }
  }

  if (isLoading) {
    return (
      <div className="empty-state">
        <span className="spinner" />
      </div>
    );
  }

  if (error || !set) {
    return <div className="alert alert-error">⚠️ Set not found.</div>;
  }

  return (
    <div>
      <p className="muted" style={{ marginBottom: '0.75rem' }}>
        <Link to="/sets">My Sets</Link> / {set.name}
      </p>

      {actionError && <div className="alert alert-error">⚠️ {actionError}</div>}
      {actionMessage && <div className="alert alert-success">✅ {actionMessage}</div>}

      <div className="detail-grid">
        <div>
          <h1>{set.name}</h1>
          <p className="muted">
            Set #{set.setNumber} · {set.year ?? '—'} · {set.theme ?? '—'} · {set.pieces ?? '—'} pcs
          </p>

          <div className="card" style={{ padding: '1rem', marginBottom: '1rem' }}>
            <h3>Build progress</h3>
            <form onSubmit={saveProgress} style={{ display: 'flex', gap: '0.75rem', alignItems: 'end', flexWrap: 'wrap' }}>
              <div className="field" style={{ marginBottom: 0 }}>
                <label>Status</label>
                <select value={buildStatus} onChange={(e) => setBuildStatus(e.target.value)}>
                  {OWNED_BUILD_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {BUILD_STATUS_META[s].label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field" style={{ marginBottom: 0 }}>
                <label>Current page</label>
                <input
                  type="number"
                  min={0}
                  value={buildPage}
                  onChange={(e) => setBuildPage(e.target.value)}
                  style={{ width: '6rem' }}
                />
              </div>
              <button className="btn btn-primary" type="submit" disabled={savingProgress}>
                {savingProgress ? <span className="spinner" /> : 'Save progress'}
              </button>
            </form>
          </div>

          <div className="card" style={{ padding: '1rem', marginBottom: '1rem' }}>
            <h3>Location</h3>
            <p className="muted" style={{ fontSize: '0.82rem' }}>
              Where this set is stored once it's complete.
            </p>
            <form onSubmit={saveLocation} style={{ display: 'flex', gap: '0.75rem', alignItems: 'end' }}>
              <div className="field" style={{ marginBottom: 0, flex: 1 }}>
                <label>Location</label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  list="location-options"
                  placeholder="e.g. Shelf 3, Bin A"
                />
                <datalist id="location-options">
                  {data.locations.map((l) => (
                    <option key={l} value={l} />
                  ))}
                </datalist>
              </div>
              <button className="btn btn-primary" type="submit" disabled={savingLocation}>
                {savingLocation ? <span className="spinner" /> : 'Save location'}
              </button>
            </form>
          </div>

          {set.label_url && (
            <div style={{ marginBottom: '1rem' }}>
              <a className="btn btn-outline btn-sm" href={set.label_url} target="_blank" rel="noreferrer">
                🏷 Show label
              </a>
            </div>
          )}

          {isAdmin && (
            <div className="row-actions">
              <button className="btn btn-outline btn-sm" onClick={() => setShowEditModal(true)}>
                ✏️ Edit set
              </button>
              {set.setID > 0 && (
                <button className="btn btn-outline btn-sm" onClick={refreshFromBrickset}>
                  🔄 Refresh from Brickset
                </button>
              )}
              {!showDeleteConfirm ? (
                <button className="btn btn-danger-outline btn-sm" onClick={() => setShowDeleteConfirm(true)}>
                  🗑 Delete set
                </button>
              ) : (
                <span style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.82rem' }}>Delete this set?</span>
                  <button className="btn btn-sm" onClick={() => setShowDeleteConfirm(false)}>
                    Cancel
                  </button>
                  <button className="btn btn-primary btn-sm" style={{ background: 'var(--color-danger)' }} onClick={deleteSet}>
                    Confirm delete
                  </button>
                </span>
              )}
            </div>
          )}

          {!set.local_instructions?.length ? (
            <div className="alert alert-error" style={{ marginTop: '1.5rem' }}>
              ⚠️ No instructions found for this set yet. Brickset may not have published them, or the download
              may have failed.
            </div>
          ) : (
            <div style={{ marginTop: '1.5rem' }}>
              <h3>Instructions</h3>
              <Suspense fallback={<div className="card" style={{ padding: '1rem' }}><span className="spinner" /> Loading viewer…</div>}>
                <PdfViewer
                  urls={set.local_instruction_urls ?? []}
                  setId={set.setID}
                  initialPage={set.build_page ?? 0}
                />
              </Suspense>
            </div>
          )}
        </div>

        <div>
          <div className="set-thumb-wrap card">
            {set.image ? <img src={set.image} alt={set.name} /> : <span style={{ fontSize: '3rem' }}>📦</span>}
          </div>
        </div>
      </div>

      {showEditModal && (
        <EditSetModal
          setId={set.setID}
          initialName={set.name}
          initialYear={set.year}
          initialTheme={set.theme}
          initialPieces={set.pieces}
          instructionsCount={set.local_instructions?.length ?? 0}
          onClose={() => setShowEditModal(false)}
          onSaved={() => {
            setShowEditModal(false);
            queryClient.invalidateQueries({ queryKey: ['set-detail', setId] });
          }}
        />
      )}
    </div>
  );
}

function EditSetModal({
  setId,
  initialName,
  initialYear,
  initialTheme,
  initialPieces,
  instructionsCount,
  onClose,
  onSaved,
}: {
  setId: number;
  initialName: string;
  initialYear: number | null;
  initialTheme: string | null;
  initialPieces: number | null;
  instructionsCount: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(initialName);
  const [year, setYear] = useState(initialYear ? String(initialYear) : '');
  const [theme, setTheme] = useState(initialTheme ?? '');
  const [pieces, setPieces] = useState(initialPieces ? String(initialPieces) : '');
  const [instructions, setInstructions] = useState<FileList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError('Name is required.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('name', name.trim());
      if (year) form.append('year', year);
      if (theme) form.append('theme', theme);
      if (pieces) form.append('pieces', pieces);
      if (instructions) Array.from(instructions).forEach((f) => form.append('instructions', f));
      await api.post(`/sets/${setId}/edit`, form);
      onSaved();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to save changes.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>✏️ Edit set</h3>
          <button className="modal-close" onClick={onClose}>
            ✕
          </button>
        </div>
        {error && <div className="alert alert-error">⚠️ {error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Name *</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <div className="field" style={{ flex: 1 }}>
              <label>Year</label>
              <input type="number" value={year} onChange={(e) => setYear(e.target.value)} />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label>Pieces</label>
              <input type="number" value={pieces} onChange={(e) => setPieces(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label>Theme</label>
            <input type="text" value={theme} onChange={(e) => setTheme(e.target.value)} />
          </div>
          <div className="field">
            <label>Add instruction PDFs</label>
            <input type="file" accept="application/pdf" multiple onChange={(e) => setInstructions(e.target.files)} />
            {instructionsCount > 0 && (
              <small className="muted">
                This set already has {instructionsCount} instruction file(s). New uploads are added alongside them.
              </small>
            )}
          </div>
          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? <span className="spinner" /> : 'Save changes'}
          </button>
        </form>
      </div>
    </div>
  );
}
