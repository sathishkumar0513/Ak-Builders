import { useQuery } from '@tanstack/react-query';
import { settingsApi } from '@/api/services';

/** States, units and payment modes from the server (cached for the session). */
export function useLookups() {
  const { data } = useQuery({
    queryKey: ['lookups'],
    queryFn: settingsApi.lookups,
    staleTime: Infinity,
  });
  return data || { states: [], units: [], payment_modes: [] };
}

export function useCompany() {
  const { data } = useQuery({
    queryKey: ['company'],
    queryFn: settingsApi.company,
    staleTime: 5 * 60_000,
  });
  return data;
}
