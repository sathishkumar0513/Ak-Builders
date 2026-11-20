import { createContext, useCallback, useContext, useRef, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import Modal from './Modal';

const ConfirmContext = createContext(null);

/**
 * const confirm = useConfirm();
 * if (await confirm({ title: 'Deactivate user?', message: '...', confirmText: 'Deactivate', danger: true })) { ... }
 */
export function ConfirmProvider({ children }) {
  const [state, setState] = useState(null);
  const resolver = useRef(null);

  const confirm = useCallback(
    (options) =>
      new Promise((resolve) => {
        resolver.current = resolve;
        setState(options);
      }),
    [],
  );

  const close = (result) => {
    resolver.current?.(result);
    resolver.current = null;
    setState(null);
  };

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Modal
        open={!!state}
        onClose={() => close(false)}
        title={state?.title || 'Are you sure?'}
        size="sm"
        footer={
          <>
            <button className="btn-secondary" onClick={() => close(false)}>
              {state?.cancelText || 'Cancel'}
            </button>
            <button
              className={state?.danger ? 'btn-danger' : 'btn-primary'}
              onClick={() => close(true)}
              autoFocus
            >
              {state?.confirmText || 'Confirm'}
            </button>
          </>
        }
      >
        <div className="flex gap-3">
          {state?.danger && <AlertTriangle className="mt-0.5 shrink-0 text-red-600" size={20} />}
          <p className="text-sm text-slate-600 dark:text-slate-300">{state?.message}</p>
        </div>
      </Modal>
    </ConfirmContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error('useConfirm must be used inside <ConfirmProvider>');
  return ctx;
}
