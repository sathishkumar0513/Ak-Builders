import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Plus, X } from 'lucide-react';
import clsx from 'clsx';
import { useClickOutside } from '@/hooks/useClickOutside';

/**
 * Searchable dropdown: the field itself is the search box — click (or tab in) and type.
 * Keyboard: ↑ ↓ to move, Enter to choose, Esc to close (without closing the form around it).
 *
 * options:      [{ value, label }]
 * allowCustom:  also accept a typed value that isn't in the list (e.g. a village). Leaving the
 *               field after typing keeps what was typed.
 * clearable:    show an × to empty the value
 */
export default function SearchSelect({
  value,
  onChange,
  options = [],
  placeholder = 'Select',
  invalid,
  allowCustom = false,
  clearable = false,
  disabled,
  emptyText = 'No matches',
  name,
  onBlur,
  className,
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(null); // null = not typing, show the selected label
  const [active, setActive] = useState(0);
  const [dropUp, setDropUp] = useState(false);
  const ref = useRef(null);
  const listRef = useRef(null);
  const listId = useId();

  const selected = options.find((o) => String(o.value) === String(value ?? ''));
  const shown = selected?.label ?? (allowCustom && value ? String(value) : '');

  const filtered = useMemo(() => {
    const q = (query || '').trim().toLowerCase();
    if (!q) return options;
    const starts = [];
    const contains = [];
    options.forEach((o) => {
      const l = String(o.label).toLowerCase();
      if (l.startsWith(q)) starts.push(o);
      else if (l.includes(q)) contains.push(o);
    });
    return [...starts, ...contains];
  }, [options, query]);

  const typed = (query || '').trim();
  const exact = options.find((o) => String(o.label).toLowerCase() === typed.toLowerCase());
  const items =
    allowCustom && typed && !exact
      ? [...filtered, { value: typed, label: typed, custom: true }]
      : filtered;

  const close = (commitTyped) => {
    const t = (query || '').trim();
    if (commitTyped && allowCustom && t && t !== shown) onChange(exact ? exact.value : t);
    setOpen(false);
    setQuery(null);
    onBlur?.();
  };

  // click, tap or tab outside closes (and keeps a typed city)
  useClickOutside(ref, () => close(true), open);

  // open upwards when the list would be cut off by the bottom of the screen / dialog
  useEffect(() => {
    if (!open || !ref.current) return;
    const box = ref.current.getBoundingClientRect();
    let bottom = window.innerHeight;
    let top = 0;
    for (let el = ref.current.parentElement; el; el = el.parentElement) {
      const oy = getComputedStyle(el).overflowY;
      if (oy === 'auto' || oy === 'scroll' || oy === 'hidden') {
        const r = el.getBoundingClientRect();
        bottom = Math.min(bottom, r.bottom);
        top = Math.max(top, r.top);
        break;
      }
    }
    const below = bottom - box.bottom;
    setDropUp(below < 250 && box.top - top > below);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const i = typed ? 0 : options.findIndex((o) => String(o.value) === String(value ?? ''));
    setActive(Math.max(i, 0));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, query]);

  useEffect(() => {
    if (open) {
      listRef.current
        ?.querySelector(`[data-index="${active}"]`)
        ?.scrollIntoView({ block: 'nearest' });
    }
  }, [active, open]);

  const choose = (o) => {
    onChange(o.value);
    setOpen(false);
    setQuery(null);
    onBlur?.();
  };

  const onKey = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!open) setOpen(true);
      else setActive((a) => Math.min(a + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === 'Enter') {
      if (!open) return;
      e.preventDefault(); // never submit the form from here
      if (items[active]) choose(items[active]);
      else close(true);
    } else if (e.key === 'Escape' && open) {
      // close only this list, not the modal around it
      e.preventDefault();
      e.stopPropagation();
      e.nativeEvent.stopImmediatePropagation();
      setOpen(false);
      setQuery(null);
    } else if (e.key === 'Tab' && open) {
      // typed something → take the highlighted suggestion (like Enter); otherwise just leave
      if (typed && items[active]) choose(items[active]);
      else close(false);
    }
  };

  return (
    <div className={clsx('relative', className)} ref={ref}>
      <input
        name={name}
        disabled={disabled}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        // while open the field is an empty search box; the current choice stays visible as a hint
        value={open ? (query ?? '') : shown}
        placeholder={open ? shown || 'Type to search…' : placeholder}
        onFocus={() => {
          setOpen(true);
          setQuery('');
        }}
        onClick={() => {
          if (!open) {
            setOpen(true);
            setQuery('');
          }
        }}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onKeyDown={onKey}
        className={clsx(
          'input pr-14',
          open && shown && 'placeholder:text-slate-500 dark:placeholder:text-slate-300',
          invalid && 'border-red-500',
          disabled && 'cursor-not-allowed opacity-60',
        )}
      />
      <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center gap-1 text-slate-400">
        {clearable && value && !disabled && (
          <button
            type="button"
            tabIndex={-1}
            aria-label="Clear"
            className="pointer-events-auto rounded p-0.5 hover:text-slate-600"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              onChange('');
              setQuery(null);
            }}
          >
            <X size={15} />
          </button>
        )}
        <ChevronDown size={16} className={clsx('transition', open && 'rotate-180')} />
      </span>

      {open && (
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          className={clsx(
            'absolute z-30 max-h-60 w-full min-w-[12rem] overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-lg dark:border-slate-700 dark:bg-slate-800',
            dropUp ? 'bottom-full mb-1' : 'mt-1',
          )}
        >
          {items.map((o, i) => {
            const isSel = !o.custom && String(o.value) === String(value ?? '');
            return (
              <li
                key={`${o.custom ? 'custom-' : ''}${o.value}`}
                data-index={i}
                role="option"
                aria-selected={isSel}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(o)}
                className={clsx(
                  'flex cursor-pointer items-center justify-between gap-2 px-3 py-2',
                  i === active && 'bg-brand-50 dark:bg-slate-700',
                )}
              >
                <span className="flex items-center gap-2 truncate">
                  {o.custom && <Plus size={14} className="shrink-0 text-brand-600" />}
                  {o.custom ? (
                    <span>
                      Use “<b>{o.label}</b>”
                    </span>
                  ) : (
                    o.label
                  )}
                </span>
                {isSel && <Check size={15} className="shrink-0 text-brand-600" />}
              </li>
            );
          })}
          {items.length === 0 && (
            <li className="px-3 py-3 text-center text-slate-500">
              {allowCustom ? 'Type a name to add it' : emptyText}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
