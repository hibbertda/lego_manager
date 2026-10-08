import { Archive, CheckCircle2, Circle, Star, Wrench } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// Mirrors BUILD_STATUS_META's keys in constants.ts — kept as a separate
// (TSX) module since JSX/components can't live in a plain .ts file.
export const STATUS_ICONS: Record<string, LucideIcon> = {
  not_started: Circle,
  in_progress: Wrench,
  complete: CheckCircle2,
  storage: Archive,
  wishlist: Star,
};
