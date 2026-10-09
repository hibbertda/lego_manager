import { useInfiniteQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { SetListResponse } from '../types';

export interface SetsFilters {
  view: 'grid' | 'list';
  theme: string;
  status: string;
  location: string;
  favorite: boolean;
  sort: string;
}

export function useInfiniteSets(mode: 'sets' | 'wishlist', filters: SetsFilters) {
  const endpoint = mode === 'wishlist' ? '/wishlist' : '/sets';

  return useInfiniteQuery({
    queryKey: ['sets-list', mode, filters],
    queryFn: async ({ pageParam }) => {
      const params: Record<string, string> = {
        view: filters.view,
        theme: filters.theme,
        sort: filters.sort,
        page: String(pageParam),
      };
      if (filters.favorite) params.favorite = '1';
      if (mode === 'sets') {
        if (filters.status) params.status = filters.status;
        if (filters.location) params.location = filters.location;
      }
      const { data } = await api.get<SetListResponse>(endpoint, { params });
      return data;
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined),
  });
}
