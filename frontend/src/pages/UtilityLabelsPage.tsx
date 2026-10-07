import { useQuery } from '@tanstack/react-query';
import { Link, NavLink } from 'react-router-dom';
import { api } from '../api/client';
import type { SetSummary } from '../types';

interface LabelsResponse {
  sets: SetSummary[];
  base_url_configured: boolean;
}

function UtilityTabs() {
  return (
    <div className="tabs">
      <NavLink to="/utility/labels" className={({ isActive }) => (isActive ? 'active' : '')}>
        Labels
      </NavLink>
      <NavLink to="/utility/missing-metadata" className={({ isActive }) => (isActive ? 'active' : '')}>
        Missing Metadata
      </NavLink>
    </div>
  );
}

export { UtilityTabs };

export default function UtilityLabelsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['utility-labels'],
    queryFn: async () => (await api.get<LabelsResponse>('/utility/labels')).data,
  });

  return (
    <div>
      <h1>🛠 Utility — Labels</h1>
      <UtilityTabs />

      {!isLoading && !data?.base_url_configured && (
        <div className="alert alert-error">
          ⚠️ APP_BASE_URL isn't configured, so storage-box labels can't be generated yet. Ask an administrator to
          set it.
        </div>
      )}

      {isLoading ? (
        <span className="spinner" />
      ) : data && data.sets.length > 0 ? (
        <div className="sets-grid">
          {data.sets.map((s) => (
            <div key={s.setID} className="card" style={{ padding: '0.75rem' }}>
              <div className="set-name">{s.name}</div>
              <div className="set-meta">#{s.setNumber}</div>
              <div className="row-actions" style={{ marginTop: '0.5rem' }}>
                {s.label_image_url && (
                  <>
                    <a className="btn btn-sm btn-outline" href={s.label_image_url} target="_blank" rel="noreferrer">
                      View label
                    </a>
                    <a className="btn btn-sm btn-outline" href={`${s.label_image_url}?download=1`}>
                      Download
                    </a>
                  </>
                )}
                <Link className="btn btn-sm btn-outline" to={`/sets/${s.setID}`}>
                  Open set
                </Link>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <p>No labels generated yet.</p>
        </div>
      )}
    </div>
  );
}
