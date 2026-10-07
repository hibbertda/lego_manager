import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { SearchResponse } from '../types';
import SetCard from '../components/SetCard';

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('query') ?? '';
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['search', query, page],
    queryFn: async () => {
      const { data } = await api.get<SearchResponse>('/search', { params: { query, page } });
      return data;
    },
    enabled: !!query,
  });

  const sets = useMemo(() => data?.sets ?? [], [data]);

  return (
    <div>
      <div className="page-header">
        <h1>🔍 Search results for "{query}"</h1>
      </div>

      {isLoading && (
        <div className="empty-state">
          <span className="spinner" />
        </div>
      )}

      {!isLoading && sets.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">🔍</div>
          <p>No sets matched your search.</p>
        </div>
      )}

      {sets.length > 0 && (
        <>
          <div className="sets-grid">
            {sets.map((s) => (
              <SetCard key={s.setID} set={s} view="grid" wishlistMode={false} />
            ))}
          </div>
          {data && data.total_pages > 1 && (
            <div className="toolbar" style={{ justifyContent: 'center', marginTop: '1.5rem' }}>
              <button className="btn btn-outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                ← Previous
              </button>
              <span className="muted">
                Page {data.page} of {data.total_pages}
              </span>
              <button
                className="btn btn-outline"
                disabled={page >= data.total_pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
