import { QueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { getErrorMessage } from './client';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
    mutations: { onError: (error) => toast.error(getErrorMessage(error)) },
  },
});
