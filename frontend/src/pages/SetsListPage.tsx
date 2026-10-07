import { useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useInfiniteSets, type SetsFilters } from '../hooks/useInfiniteSets';
import { SORT_LABELS, DEFAULT_SORT } from '../constants';
import FilterSidebar from '../components/FilterSidebar';
import SetCard from '../components/SetCard';

export default function SetsListPage({ mode }: { mode: 'sets' | 'wishlist' }) {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters: SetsFilters = useMemo(
    () => ({
      view: (searchParams.get('view') as 'grid' | 'list') || 'grid',
      theme: searchParams.get('theme') || '',
      status: searchParams.get('status') || '',
      location: searchParams.get('location') || '',
      favorite: searchParams.get('favorite') === '1',
      sort: searchParams.get('sort') || DEFAULT_SORT,
    }),
    [searchParams],
  );

  function updateFilters(partial: Partial<SetsFilters>) {
    const next = { ...filters, ...partial };
    const params = new URLSearchParams();
    if (next.view !== 'grid') params.set('view', next.view);
    if (next.theme) params.set('theme', next.theme);
    if (mode === 'sets' && next.status) params.set('status', next.status);
    if (mode === 'sets' && next.location) params.set('location', next.location);
    if (next.favorite) params.set('favorite', '1');
    if (next.sort !== DEFAULT_SORT) params.set('sort', next.sort);
    setSearchParams(params);
  }

  const query = useInfiniteSets(mode, filters);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && query.hasNextPage && !query.isFetchingNextPage) {
          query.fetchNextPage();
        }
      },
      { rootMargin: '400px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.hasNextPage, query.isFetchingNextPage]);

  const pages = query.data?.pages ?? [];
  const sets = pages.flatMap((p) => p.sets);
  const themes = pages[0]?.themes ?? [];
  const locations = pages[0]?.locations ?? [];
  const sortLabels = pages[0]?.sort_labels ?? SORT_LABELS;
  const total = pages[0]?.total ?? 0;

  return (
    <div>
      <div className="page-header">
        <h1>{mode === 'wishlist' ? '⭐ Wishlist' : '📦 My Sets'}</h1>
        <div className="toolbar">
          <select value={filters.sort} onChange={(e) => updateFilters({ sort: e.target.value })}>
            {Object.entries(sortLabels).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <div className="btn-group">
            <button
              className={`btn ${filters.view === 'grid' ? 'active' : ''}`}
              onClick={() => updateFilters({ view: 'grid' })}
            >
              ▦ Grid
            </button>
            <button
              className={`btn ${filters.view === 'list' ? 'active' : ''}`}
              onClick={() => updateFilters({ view: 'list' })}
            >
              ☰ List
            </button>
          </div>
        </div>
      </div>

      <div className="sets-layout">
        <FilterSidebar
          wishlistMode={mode === 'wishlist'}
          themes={themes}
          locations={locations}
          filters={filters}
          onChange={updateFilters}
        />

        <div className="sets-content">
          {query.isLoading && (
            <div className="empty-state">
              <span className="spinner" />
            </div>
          )}

          {!query.isLoading && sets.length === 0 && (
            <div className="empty-state">
              <div className="empty-icon">{mode === 'wishlist' ? '⭐' : '📦'}</div>
              {mode === 'wishlist' ? (
                <p>No sets on your wishlist yet. Add one via "Add a Set" and pick the Wishlist category.</p>
              ) : (
                <p>No sets yet. Use "Add a Set" in the sidebar to add your first one.</p>
              )}
            </div>
          )}

          {sets.length > 0 && (
            <>
              <p className="muted" style={{ marginBottom: '0.75rem', fontSize: '0.85rem' }}>
                {total} set{total === 1 ? '' : 's'}
              </p>
              <div className={filters.view === 'grid' ? 'sets-grid' : 'set-list'}>
                {sets.map((s) => (
                  <SetCard key={s.setID} set={s} view={filters.view} wishlistMode={mode === 'wishlist'} />
                ))}
              </div>
              <div ref={sentinelRef} className="sentinel">
                {query.isFetchingNextPage && <span className="spinner" />}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
