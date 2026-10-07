import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api, extractErrorMessage } from '../api/client';
import type { SetSummary } from '../types';
import { UtilityTabs } from './UtilityLabelsPage';

interface MissingMetadataResult extends SetSummary {
  missing_fields: string[];
}

interface MissingMetadataResponse {
  results: MissingMetadataResult[];
  base_url_configured: boolean;
}

export default function UtilityMissingMetadataPage() {
  const [data, setData] = useState<MissingMetadataResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => (await api.post<MissingMetadataResponse>('/utility/missing-metadata/run')).data,
    onSuccess: (result) => {
      setData(result);
      setError(null);
    },
    onError: (err) => setError(extractErrorMessage(err, 'Failed to run the metadata scan.')),
  });

  return (
    <div>
      <h1>🛠 Utility — Missing Metadata</h1>
      <UtilityTabs />

      <p className="text-muted">
        Scan all owned sets and flag any that are missing a name, year, theme, piece count, image, or label.
      </p>

      <button className="btn btn-primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
        {mutation.isPending ? 'Scanning…' : 'Run scan'}
      </button>

      {error && (
        <div className="alert alert-error" style={{ marginTop: '1rem' }}>
          {error}
        </div>
      )}

      {data && (
        <div style={{ marginTop: '1.5rem' }}>
          {!data.base_url_configured && (
            <div className="alert alert-error">
              ⚠️ APP_BASE_URL isn't configured, so missing labels can't be detected or generated.
            </div>
          )}
          {data.results.length === 0 ? (
            <div className="empty-state">
              <p>✅ Nothing missing — all sets look complete.</p>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Set</th>
                  <th>Missing</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.results.map((s) => (
                  <tr key={s.setID}>
                    <td>
                      {s.name} <span className="text-muted">#{s.setNumber}</span>
                    </td>
                    <td>
                      {s.missing_fields.map((f) => (
                        <span key={f} className="badge badge-warning" style={{ marginRight: '0.25rem' }}>
                          {f}
                        </span>
                      ))}
                    </td>
                    <td>
                      <Link className="btn btn-sm btn-outline" to={`/sets/${s.setID}`}>
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
