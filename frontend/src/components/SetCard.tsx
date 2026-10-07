import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { BUILD_STATUS_META, OWNED_BUILD_STATUSES } from '../constants';
import type { SetSummary } from '../types';

interface Props {
  set: SetSummary;
  view: 'grid' | 'list';
  wishlistMode: boolean;
}

export default function SetCard({ set, view, wishlistMode }: Props) {
  const queryClient = useQueryClient();
  const [favorite, setFavorite] = useState(set.favorite);
  const [status, setStatus] = useState(set.build_status);
  const [statusMenuOpen, setStatusMenuOpen] = useState(false);
  const meta = BUILD_STATUS_META[status] ?? BUILD_STATUS_META.not_started;

  async function toggleFavorite(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    const { data } = await api.post<{ favorite: boolean }>(`/sets/${set.setID}/favorite`);
    setFavorite(data.favorite);
    queryClient.invalidateQueries({ queryKey: ['sets-list'] });
  }

  async function changeStatus(e: React.MouseEvent, newStatus: string) {
    e.preventDefault();
    e.stopPropagation();
    await api.post(`/sets/${set.setID}/status`, { build_status: newStatus });
    setStatus(newStatus);
    setStatusMenuOpen(false);
    queryClient.invalidateQueries({ queryKey: ['sets-list'] });
  }

  const statusBadge = !wishlistMode && (
    <div style={{ position: 'relative' }}>
      <button
        className={`badge ${meta.badgeClass}`}
        style={{ border: 'none', cursor: 'pointer' }}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setStatusMenuOpen((v) => !v);
        }}
      >
        {meta.emoji} {meta.label}
      </button>
      {statusMenuOpen && (
        <div
          className="card"
          style={{ position: 'absolute', top: '100%', left: 0, zIndex: 10, padding: '0.3rem', minWidth: '9rem' }}
          onMouseLeave={() => setStatusMenuOpen(false)}
        >
          {OWNED_BUILD_STATUSES.map((s) => (
            <button
              key={s}
              className="nav-button"
              style={{ fontSize: '0.8rem' }}
              onClick={(e) => changeStatus(e, s)}
            >
              {BUILD_STATUS_META[s].emoji} {BUILD_STATUS_META[s].label}
            </button>
          ))}
        </div>
      )}
    </div>
  );

  if (view === 'list') {
    return (
      <Link to={`/sets/${set.setID}`} className="set-list-row">
        <img
          className="set-list-thumb"
          src={set.image ?? undefined}
          alt=""
          style={!set.image ? { display: 'flex', alignItems: 'center', justifyContent: 'center' } : undefined}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="set-name">{set.name}</div>
          <div className="set-meta">
            #{set.setNumber}
            {set.year ? ` · ${set.year}` : ''}
            {set.theme ? ` · ${set.theme}` : ''}
            {set.pieces ? ` · ${set.pieces} pcs` : ''}
          </div>
        </div>
        {statusBadge}
        <button
          className={`favorite-btn ${favorite ? 'active' : ''}`}
          style={{ position: 'static' }}
          onClick={toggleFavorite}
          aria-pressed={favorite}
        >
          {favorite ? '❤️' : '🤍'}
        </button>
      </Link>
    );
  }

  return (
    <Link to={`/sets/${set.setID}`} className="set-grid-card">
      <button
        className={`favorite-btn ${favorite ? 'active' : ''}`}
        onClick={toggleFavorite}
        aria-pressed={favorite}
      >
        {favorite ? '❤️' : '🤍'}
      </button>
      <div className="set-thumb-wrap">
        {set.image ? <img src={set.image} alt="" /> : <span style={{ fontSize: '2.5rem' }}>📦</span>}
      </div>
      <div className="set-grid-card-body">
        <div className="set-name" title={set.name}>
          {set.name}
        </div>
        <div className="set-meta">
          #{set.setNumber}
          {set.year ? ` · ${set.year}` : ''}
        </div>
        {statusBadge}
      </div>
    </Link>
  );
}
