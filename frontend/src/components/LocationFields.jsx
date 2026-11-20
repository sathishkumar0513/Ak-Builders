import { useQuery } from '@tanstack/react-query';
import { settingsApi } from '@/api/services';
import { useLookups } from '@/hooks/useLookups';
import SearchSelect from '@/components/ui/SearchSelect';

/** Searchable state list (names only — the GST state code is the value). */
export function StateSelect(props) {
  const { states } = useLookups();
  return <SearchSelect options={states} placeholder="Select state" {...props} />;
}

/**
 * Searchable city list for a state: main cities of that state plus every city already used.
 * Any other place (a village, a new area) can be typed and used as it is.
 */
export function CitySelect({ stateCode = '33', ...props }) {
  const { data = [] } = useQuery({
    queryKey: ['lookups', 'cities', stateCode],
    queryFn: () => settingsApi.cities(stateCode),
    staleTime: 5 * 60_000,
    enabled: !!stateCode,
  });
  return (
    <SearchSelect
      options={data.map((c) => ({ value: c, label: c }))}
      placeholder="Select or type city"
      allowCustom
      clearable
      {...props}
    />
  );
}
