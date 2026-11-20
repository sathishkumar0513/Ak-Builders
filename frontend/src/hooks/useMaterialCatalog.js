import { useQuery } from '@tanstack/react-query';
import { materialsApi } from '@/api/services';

/** All active materials, cached — small catalogue, so filtering happens in the browser (fast on phones). */
export function useMaterialCatalog() {
  return useQuery({
    queryKey: ['materials', 'catalog'],
    queryFn: () =>
      materialsApi
        .list({ is_active: true, page_size: 200, ordering: 'name' })
        .then((d) => d.results),
    staleTime: 60_000,
  });
}
