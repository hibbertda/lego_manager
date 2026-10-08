import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, Package } from 'lucide-react';
import { api } from '../api/client';
import { BUILD_STATUS_META, OWNED_BUILD_STATUSES } from '../constants';
import { STATUS_ICONS } from '../statusIcons';
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
  const StatusIcon = STATUS_ICONS[status] ?? STATUS_ICONS.not_started;

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
        style={{ border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setStatusMenuOpen((v) => !v);
        }}
      >
        <StatusIcon size={13} /> {meta.label}
      </button>
      {statusMenuOpen && (
        <div
          className="card"
          style={{ position: 'absolute', top: '100%', left: 0, zIndex: 10, padding: '0.3rem', minWidth: '9rem' }}
          onMouseLeave={() => setStatusMenuOpen(false)}
        >
          {OWNED_BUILD_STATUSES.map((s) => {
            const ItemIcon = STATUS_ICONS[s];
            return (
              <button
                key={s}
                className="nav-button"
                style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
                onClick={(e) => changeStatus(e, s)}
              >
                <ItemIcon size={14} /> {BUILD_STATUS_META[s].label}
              </button>
            );
          })}
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
          <Heart size={16} fill={favorite ? 'currentColor' : 'none'} />
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
        <Heart size={16} fill={favorite ? 'currentColor' : 'none'} />
      </button>
      <div className="set-thumb-wrap">
        {set.image ? <img src={set.image} alt="" /> : <Package size={40} strokeWidth={1.5} className="text-muted" />}
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
