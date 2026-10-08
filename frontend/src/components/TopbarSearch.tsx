import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Package } from 'lucide-react';
import { api } from '../api/client';
import type { SuggestResponse, SuggestResult } from '../types';

export default function TopbarSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SuggestResult[] | null>(null);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults(null);
      setOpen(false);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api
        .get<SuggestResponse>('/search/suggest', { params: { query: trimmed }, signal: controller.signal })
        .then(({ data }) => {
          setResults(data.results);
          setOpen(true);
        })
        .catch(() => {});
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setOpen(false);
    navigate(`/search?query=${encodeURIComponent(query.trim())}`);
  }

  return (
    <div className="topbar-search" ref={containerRef}>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Search your sets..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results && setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setOpen(false);
          }}
        />
      </form>
      {open && results && (
        <div className="topbar-search-results">
          {results.length === 0 && <p style={{ padding: '0.6rem 0.8rem', margin: 0 }}>No matching sets found.</p>}
          {results.map((r) => (
            <a key={r.id} href={`/app/sets/${r.id}`} onClick={(e) => { e.preventDefault(); setOpen(false); navigate(`/sets/${r.id}`); }}>
              {r.image ? (
                <img src={r.image} alt="" style={{ width: '2.5rem', height: '2.5rem', objectFit: 'contain' }} />
              ) : (
                <span style={{ width: '2.5rem', height: '2.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Package size={20} strokeWidth={1.5} className="text-muted" />
                </span>
              )}
              <span>
                <span style={{ display: 'block', fontWeight: 600, fontSize: '0.85rem' }}>{r.name}</span>
                <span style={{ display: 'block', fontSize: '0.78rem', color: 'var(--color-muted)' }}>
                  #{r.setNumber}
                  {r.year ? ` · ${r.year}` : ''}
                </span>
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
