// Mirrors app/sql_ops.py's VALID_BUILD_STATUSES / OWNED_BUILD_STATUSES /
// BUILD_STATUS_META / SORT_LABELS / DEFAULT_SORT. Kept here instead of
// trusting the API response shape everywhere, since the "Add a set" modal
// needs the full status list (incl. "wishlist") even on pages whose list
// endpoint only returns the owned-subset.

export const ALL_BUILD_STATUSES = [
  'not_started',
  'in_progress',
  'complete',
  'storage',
  'wishlist',
] as const;

export const OWNED_BUILD_STATUSES = ['not_started', 'in_progress', 'complete', 'storage'] as const;

export const BUILD_STATUS_META: Record<string, { label: string; emoji: string; badgeClass: string }> = {
  not_started: { label: 'Not Started', emoji: '▫️', badgeClass: 'badge-secondary' },
  in_progress: { label: 'In Progress', emoji: '🛠', badgeClass: 'badge-warning' },
  complete: { label: 'Complete', emoji: '✅', badgeClass: 'badge-success' },
  storage: { label: 'Storage', emoji: '🗄', badgeClass: 'badge-info' },
  wishlist: { label: 'Wishlist', emoji: '⭐', badgeClass: 'badge-primary' },
};

export const DEFAULT_SORT = 'name';

export const SORT_LABELS: Record<string, string> = {
  name: 'Name (A-Z)',
  year: 'Year released (newest first)',
  theme: 'Theme (A-Z)',
};
