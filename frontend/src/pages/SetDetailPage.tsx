import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, extractErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Package,
  Pencil,
  RefreshCw,
  Tag,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import { BUILD_STATUS_META, OWNED_BUILD_STATUSES } from '../constants';
import type { SetDetailResponse, SetPartsResponse } from '../types';

const PdfViewer = lazy(() => import('../components/PdfViewer'));

export default function SetDetailPage() {
  const { setId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
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
  const [uploadingPhotos, setUploadingPhotos] = useState(false);
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const locationLoadedRef = useRef(false);
  const lastSavedLocationRef = useRef<string | null>(null);
  const locationSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const set = data?.set;

  const galleryItems: { url: string; buildIndex: number }[] = set
    ? [
        ...(set.image ? [{ url: set.image, buildIndex: -1 }] : []),
        ...(set.build_photo_urls ?? []).map((url, i) => ({ url, buildIndex: i })),
      ]
    : [];
  const activePhotoIndex = Math.min(selectedPhotoIndex, Math.max(galleryItems.length - 1, 0));
  const activePhoto = galleryItems[activePhotoIndex];

  function showPrevPhoto() {
    if (!galleryItems.length) return;
    setSelectedPhotoIndex((activePhotoIndex - 1 + galleryItems.length) % galleryItems.length);
  }

  function showNextPhoto() {
    if (!galleryItems.length) return;
    setSelectedPhotoIndex((activePhotoIndex + 1) % galleryItems.length);
  }

  // Sync local form state once the set loads (only on first load / id change).
  if (set && buildStatus === '' && buildPage === '') {
    setBuildStatus(set.build_status);
    setBuildPage(String(set.build_page ?? 0));
    setLocation(set.location ?? '');
    lastSavedLocationRef.current = set.location ?? '';
    locationLoadedRef.current = true;
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

  // Auto-saves the location a moment after the user stops typing, instead of
  // requiring an explicit save button.
  useEffect(() => {
    if (!locationLoadedRef.current) return;
    if (location === lastSavedLocationRef.current) return;
    if (locationSaveTimerRef.current) clearTimeout(locationSaveTimerRef.current);
    locationSaveTimerRef.current = setTimeout(async () => {
      setSavingLocation(true);
      setActionError(null);
      try {
        await api.post(`/sets/${setId}/location`, { location });
        lastSavedLocationRef.current = location;
        queryClient.invalidateQueries({ queryKey: ['set-detail', setId] });
      } catch (err) {
        setActionError(extractErrorMessage(err, 'Failed to update location.'));
      } finally {
        setSavingLocation(false);
      }
    }, 700);
    return () => {
      if (locationSaveTimerRef.current) clearTimeout(locationSaveTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location, setId]);

  const resolveField = searchParams.get('resolve');

  // Deep-link support from the Utility — Missing Metadata page: jump straight
  // into whatever lets an admin fix the specific missing field that was
  // clicked (edit modal, a Brickset refresh, or the parts/minifigs section).
  useEffect(() => {
    if (!set || !resolveField) return;
    if (isAdmin) {
      if (resolveField === 'cover image' && set.setID > 0) {
        refreshFromBrickset();
      } else if (resolveField === 'parts' || resolveField === 'minifigs') {
        document
          .getElementById('parts-minifigs-section')
          ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else {
        setShowEditModal(true);
      }
    }
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete('resolve');
        return next;
      },
      { replace: true },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [set?.setID, resolveField, isAdmin]);

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

  async function uploadPhotos(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploadingPhotos(true);
    setActionError(null);
    try {
      const form = new FormData();
      Array.from(files).forEach((f) => form.append('photos', f));
      await api.post(`/sets/${setId}/photos`, form);
      queryClient.invalidateQueries({ queryKey: ['set-detail', setId] });
      setActionMessage('Photo(s) uploaded.');
    } catch (err) {
      setActionError(extractErrorMessage(err, 'Failed to upload photo(s).'));
    } finally {
      setUploadingPhotos(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
      if (cameraInputRef.current) cameraInputRef.current.value = '';
    }
  }

  async function deletePhoto(path: string) {
    setActionError(null);
    try {
      await api.delete(`/sets/${setId}/photos`, { data: { path } });
      queryClient.invalidateQueries({ queryKey: ['set-detail', setId] });
      setSelectedPhotoIndex(0);
    } catch (err) {
      setActionError(extractErrorMessage(err, 'Failed to delete photo.'));
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
    return (
      <div className="alert alert-error">
        <AlertTriangle size={15} /> Set not found.
      </div>
    );
  }

  return (
    <div>
      <p className="muted" style={{ marginBottom: '0.75rem' }}>
        <Link to="/sets">My Sets</Link> / {set.name}
      </p>

      {actionError && (
        <div className="alert alert-error">
          <AlertTriangle size={15} /> {actionError}
        </div>
      )}
      {actionMessage && (
        <div className="alert alert-success">
          <CheckCircle2 size={15} /> {actionMessage}
        </div>
      )}

      <div className="detail-grid">
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '0.75rem', flexWrap: 'wrap' }}>
            <h1 style={{ margin: 0 }}>{set.name}</h1>
            {isAdmin && (
              <div className="row-actions" style={{ flexShrink: 0 }}>
                <button className="btn btn-outline btn-sm" onClick={() => setShowEditModal(true)}>
                  <Pencil size={14} /> Edit set
                </button>
                {set.setID > 0 && (
                  <button className="btn btn-outline btn-sm" onClick={refreshFromBrickset}>
                    <RefreshCw size={14} /> Refresh from Brickset
                  </button>
                )}
                {!showDeleteConfirm ? (
                  <button className="btn btn-danger-outline btn-sm" onClick={() => setShowDeleteConfirm(true)}>
                    <Trash2 size={14} /> Delete set
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
          </div>
          <p className="muted">
            Set #{set.setNumber} · {set.year ?? '—'} · {set.theme ?? '—'} · {set.pieces ?? '—'} pcs
          </p>

          {set.label_url && (
            <div style={{ marginBottom: '1rem' }}>
              <a className="btn btn-outline btn-sm" href={set.label_url} target="_blank" rel="noreferrer">
                <Tag size={14} /> Show label
              </a>
            </div>
          )}

          <div style={{ marginTop: '1.5rem' }}>
            <h3>Instructions</h3>
            {!set.local_instructions?.length ? (
              <div className="card pdf-viewer-card pdf-viewer-empty">
                <AlertTriangle size={26} className="text-muted" />
                <p>No instructions found for this set yet.</p>
                <p className="muted" style={{ fontSize: '0.8rem' }}>
                  Brickset may not have published them, or the download may have failed.
                </p>
              </div>
            ) : (
              <Suspense fallback={<div className="card" style={{ padding: '1rem' }}><span className="spinner" /> Loading viewer…</div>}>
                <PdfViewer
                  urls={set.local_instruction_urls ?? []}
                  setId={set.setID}
                  initialPage={set.build_page ?? 0}
                />
              </Suspense>
            )}
          </div>

          <PartsAndMinifigs setId={set.setID} isAdmin={isAdmin} />

        </div>

        <div>
          <div className="set-thumb-wrap set-thumb-wrap-lg card">
            {activePhoto ? (
              <img src={activePhoto.url} alt={set.name} />
            ) : (
              <Package size={48} strokeWidth={1.5} className="text-muted" />
            )}
            {galleryItems.length > 1 && (
              <>
                <button type="button" className="photo-nav photo-nav-prev" aria-label="Previous photo" onClick={showPrevPhoto}>
                  <ChevronLeft size={20} />
                </button>
                <button type="button" className="photo-nav photo-nav-next" aria-label="Next photo" onClick={showNextPhoto}>
                  <ChevronRight size={20} />
                </button>
              </>
            )}
          </div>

          {galleryItems.length > 1 && (
            <div className="build-photo-grid" style={{ marginTop: '0.6rem' }}>
              {galleryItems.map((item, i) => (
                <div
                  key={item.url}
                  className={`build-photo-thumb${i === activePhotoIndex ? ' is-active' : ''}`}
                  onClick={() => setSelectedPhotoIndex(i)}
                >
                  <img src={item.url} alt={item.buildIndex === -1 ? set.name : `Build photo ${item.buildIndex + 1}`} />
                  {item.buildIndex >= 0 && (
                    <button
                      type="button"
                      className="build-photo-remove"
                      aria-label="Delete photo"
                      onClick={(e) => {
                        e.stopPropagation();
                        deletePhoto(set.build_photos?.[item.buildIndex] ?? '');
                      }}
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="card" style={{ padding: '1rem', marginTop: '0.75rem' }}>
            <p className="muted" style={{ fontSize: '0.82rem', marginTop: 0 }}>
              Snap or upload photos of your completed build.
            </p>
            <div className="row-actions">
              <button
                type="button"
                className="btn btn-outline btn-sm"
                disabled={uploadingPhotos}
                onClick={() => fileInputRef.current?.click()}
              >
                {uploadingPhotos ? <span className="spinner" /> : <Upload size={14} />} Upload photos
              </button>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                disabled={uploadingPhotos}
                onClick={() => cameraInputRef.current?.click()}
              >
                <Camera size={14} /> Take photo
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              style={{ display: 'none' }}
              onChange={(e) => uploadPhotos(e.target.files)}
            />
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              style={{ display: 'none' }}
              onChange={(e) => uploadPhotos(e.target.files)}
            />
          </div>

          <div className="card" style={{ padding: '1rem', marginTop: '0.75rem' }}>
            <h3>Build progress &amp; location</h3>
            <form onSubmit={saveProgress} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '0.9rem' }}>
              <div className="field" style={{ marginBottom: 0 }}>
                <label>Status</label>
                <select
                  value={buildStatus}
                  onChange={(e) => setBuildStatus(e.target.value)}
                  style={{ width: 'auto', minWidth: '12rem' }}
                >
                  {OWNED_BUILD_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {BUILD_STATUS_META[s].label}
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'end' }}>
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
              </div>
            </form>

            <div className="field" style={{ marginBottom: 0 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                Location
                {savingLocation && <span className="spinner" style={{ width: '0.8rem', height: '0.8rem' }} />}
              </label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                list="location-options"
                placeholder="e.g. Shelf 3, Bin A"
                style={{ width: 'auto', minWidth: '12rem' }}
              />
              <datalist id="location-options">
                {data.locations.map((l) => (
                  <option key={l} value={l} />
                ))}
              </datalist>
            </div>
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

function PartsAndMinifigs({ setId, isAdmin }: { setId: number; isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['set-parts', setId],
    queryFn: async () => (await api.get<SetPartsResponse>(`/sets/${setId}/parts`)).data,
  });

  async function syncParts() {
    setSyncing(true);
    setSyncError(null);
    try {
      await api.post(`/sets/${setId}/parts/sync`);
      queryClient.invalidateQueries({ queryKey: ['set-parts', setId] });
    } catch (err) {
      setSyncError(extractErrorMessage(err, 'Failed to sync parts from Rebrickable.'));
    } finally {
      setSyncing(false);
    }
  }

  if (isLoading) {
    return (
      <div style={{ marginTop: '1.5rem' }}>
        <span className="spinner" />
      </div>
    );
  }

  const parts = data?.parts ?? [];
  const minifigs = data?.minifigs ?? [];

  return (
    <div id="parts-minifigs-section" style={{ marginTop: '1.5rem', scrollMarginTop: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
        <h3 style={{ margin: 0 }}>Parts &amp; minifigs</h3>
        {isAdmin && data?.rebrickable_configured && (
          <button className="btn btn-outline btn-sm" onClick={syncParts} disabled={syncing}>
            {syncing ? <span className="spinner" /> : <RefreshCw size={14} />}
            {data?.synced ? 'Resync from Rebrickable' : 'Fetch from Rebrickable'}
          </button>
        )}
      </div>

      {syncError && (
        <div className="alert alert-error" style={{ marginTop: '0.5rem' }}>
          <AlertTriangle size={15} /> {syncError}
        </div>
      )}

      {!data?.rebrickable_configured ? (
        <div className="card" style={{ padding: '1rem', marginTop: '0.5rem' }}>
          <p className="muted" style={{ margin: 0 }}>
            {isAdmin ? (
              <>Configure a Rebrickable API key under <Link to="/admin/rebrickable">Admin — Rebrickable API</Link> to fetch this set&apos;s parts and minifigs.</>
            ) : (
              'Parts and minifigs aren\u2019t available yet — ask an admin to configure the Rebrickable API.'
            )}
          </p>
        </div>
      ) : !data?.synced ? (
        <div className="card" style={{ padding: '1rem', marginTop: '0.5rem' }}>
          <p className="muted" style={{ margin: 0 }}>
            {isAdmin
              ? 'No parts list fetched yet for this set.'
              : 'No parts list has been fetched yet for this set.'}
          </p>
        </div>
      ) : (
        <div className="parts-minifigs-grid" style={{ marginTop: '0.5rem' }}>
          <div>
            <h4 style={{ margin: '0 0 0.4rem' }}>Parts ({parts.length})</h4>
            {parts.length === 0 ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>No parts found for this set.</p>
            ) : (
              <div className="part-tile-scroll">
                <div className="part-tile-grid">
                  {parts.map((part) => (
                    <div key={`${part.part_num}-${part.color_name}`} className="part-tile">
                      <div className="part-tile-img">
                        {part.image_url ? (
                          <img src={part.image_url} alt={part.name} loading="lazy" />
                        ) : (
                          <Package size={24} strokeWidth={1.5} className="text-muted" />
                        )}
                      </div>
                      <div className="part-tile-info">
                        <span className="part-tile-id">{part.part_num}</span>
                        <span className="part-tile-qty">×{part.quantity}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div>
            <h4 style={{ margin: '0 0 0.4rem' }}>Minifigs ({minifigs.length})</h4>
            {minifigs.length === 0 ? (
              <p className="muted" style={{ fontSize: '0.85rem' }}>No minifigs in this set.</p>
            ) : (
              <div className="part-tile-scroll">
                <div className="minifig-tile-grid">
                  {minifigs.map((fig) => (
                    <div key={fig.fig_num} className="part-tile">
                      <div className="part-tile-img">
                        {fig.image_url ? (
                          <img src={fig.image_url} alt={fig.name} loading="lazy" />
                        ) : (
                          <Package size={24} strokeWidth={1.5} className="text-muted" />
                        )}
                      </div>
                      <div className="part-tile-info">
                        <span className="part-tile-id">{fig.fig_num}</span>
                        <span className="part-tile-qty">×{fig.quantity}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
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
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Pencil size={18} /> Edit set
          </h3>
          <button className="modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        {error && (
          <div className="alert alert-error">
            <AlertTriangle size={15} /> {error}
          </div>
        )}
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
