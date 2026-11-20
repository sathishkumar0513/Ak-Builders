import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Keeps list state (page, search, ordering, filters) in the URL so it survives refresh
 * and can be shared. Returns params ready for the API.
 */
export function useListParams(defaults = {}) {
  const [searchParams, setSearchParams] = useSearchParams();

  const params = useMemo(() => {
    const obj = { page: 1, page_size: 20, ...defaults };
    searchParams.forEach((value, key) => {
      obj[key] = value;
    });
    obj.page = Number(obj.page) || 1;
    obj.page_size = Number(obj.page_size) || 20;
    return obj;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const setParams = useCallback(
    (changes, { resetPage = true } = {}) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          Object.entries(changes).forEach(([k, v]) => {
            if (v === '' || v === null || v === undefined) next.delete(k);
            else next.set(k, String(v));
          });
          if (resetPage && !('page' in changes)) next.delete('page');
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  /** Click a column: asc → desc → none */
  const toggleOrdering = useCallback(
    (field) => {
      const current = params.ordering;
      const next = current === field ? `-${field}` : current === `-${field}` ? '' : field;
      setParams({ ordering: next });
    },
    [params.ordering, setParams],
  );

  return { params, setParams, toggleOrdering };
}
