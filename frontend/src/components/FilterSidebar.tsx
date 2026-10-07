import type { SetsFilters } from '../hooks/useInfiniteSets';
import { BUILD_STATUS_META, OWNED_BUILD_STATUSES } from '../constants';

interface Props {
  wishlistMode: boolean;
  themes: string[];
  locations: string[];
  filters: SetsFilters;
  onChange: (partial: Partial<SetsFilters>) => void;
}

export default function FilterSidebar({ wishlistMode, themes, locations, filters, onChange }: Props) {
  return (
    <div className="sets-filters">
      <div className="card filter-group" style={{ padding: '0.6rem' }}>
        <h3>Theme</h3>
        <div className="filter-list">
          <a
            href="#"
            className={!filters.theme ? 'active' : ''}
            onClick={(e) => {
              e.preventDefault();
              onChange({ theme: '' });
            }}
          >
            All themes
          </a>
          {themes.map((t) => (
            <a
              key={t}
              href="#"
              className={filters.theme === t ? 'active' : ''}
              onClick={(e) => {
                e.preventDefault();
                onChange({ theme: t });
              }}
            >
              {t}
            </a>
          ))}
        </div>
      </div>

      {!wishlistMode && (
        <>
          <div className="card filter-group" style={{ padding: '0.6rem' }}>
            <h3>Status</h3>
            <div className="filter-list">
              <a
                href="#"
                className={!filters.status ? 'active' : ''}
                onClick={(e) => {
                  e.preventDefault();
                  onChange({ status: '' });
                }}
              >
                All statuses
              </a>
              {OWNED_BUILD_STATUSES.map((s) => (
                <a
                  key={s}
                  href="#"
                  className={filters.status === s ? 'active' : ''}
                  onClick={(e) => {
                    e.preventDefault();
                    onChange({ status: s });
                  }}
                >
                  {BUILD_STATUS_META[s].emoji} {BUILD_STATUS_META[s].label}
                </a>
              ))}
            </div>
          </div>

          <div className="card filter-group" style={{ padding: '0.6rem' }}>
            <h3>Location</h3>
            <div className="filter-list">
              <a
                href="#"
                className={!filters.location ? 'active' : ''}
                onClick={(e) => {
                  e.preventDefault();
                  onChange({ location: '' });
                }}
              >
                All locations
              </a>
              {locations.map((l) => (
                <a
                  key={l}
                  href="#"
                  className={filters.location === l ? 'active' : ''}
                  onClick={(e) => {
                    e.preventDefault();
                    onChange({ location: l });
                  }}
                >
                  📍 {l}
                </a>
              ))}
            </div>
          </div>
        </>
      )}

      <button
        className={`btn ${filters.favorite ? 'btn-danger-outline active' : 'btn-danger-outline'}`}
        style={{ width: '100%', justifyContent: 'center' }}
        onClick={() => onChange({ favorite: !filters.favorite })}
      >
        {filters.favorite ? '❤️ Showing favorites' : '🤍 Favorites'}
      </button>
    </div>
  );
}
