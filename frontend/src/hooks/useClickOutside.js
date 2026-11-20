import { useEffect, useRef } from 'react';

/**
 * Calls onOutside when the user clicks, taps or tabs to anything outside `ref`.
 * Listens in the capture phase, so it still works inside dialogs that stop click propagation
 * (otherwise an open dropdown in a form never hears the click on the next field).
 */
export function useClickOutside(ref, onOutside, enabled = true) {
  const cb = useRef(onOutside);
  cb.current = onOutside;
  useEffect(() => {
    if (!enabled) return undefined;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) cb.current(e);
    };
    const opts = { capture: true };
    document.addEventListener('mousedown', handler, opts);
    document.addEventListener('touchstart', handler, opts);
    document.addEventListener('focusin', handler, opts);
    return () => {
      document.removeEventListener('mousedown', handler, opts);
      document.removeEventListener('touchstart', handler, opts);
      document.removeEventListener('focusin', handler, opts);
    };
  }, [ref, enabled]);
}
