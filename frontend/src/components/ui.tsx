/* Shared design-system pieces. Pages compose these instead of styling ad hoc. */
import { useEffect, useId, useRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes,
  type TextareaHTMLAttributes } from "react";
import { Link } from "react-router-dom";
import { humanStatus } from "../lib/format";
import type { BookingStatus, ReservationStatus } from "../types";

export function PageHeader({ title, description, actions, back }: {
  title: string; description?: ReactNode; actions?: ReactNode; back?: { to: string; label: string };
}) {
  return (
    <header className="mb-8">
      {back && (
        <Link to={back.to} className="mb-3 inline-flex text-sm font-medium text-ink-500 hover:text-ink-800">
          ‹ {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-ink-900 md:text-3xl">{title}</h1>
          {description && <p className="mt-2 max-w-2xl text-sm text-ink-500 md:text-base">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </header>
  );
}

export function Panel({ children, className = "", title, actions }: {
  children: ReactNode; className?: string; title?: string; actions?: ReactNode;
}) {
  return (
    <section className={`surface rounded-2xl p-5 md:p-6 ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-base font-semibold text-ink-900">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

interface FieldShellProps {
  label: string;
  error?: string;
  hint?: string;
  children: (props: { id: string; describedBy?: string; invalid: boolean }) => ReactNode;
}

export function FieldShell({ label, error, hint, children }: FieldShellProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="label">{label}</label>
      {children({ id, describedBy, invalid: !!error })}
      {error ? (
        <p id={`${id}-error`} className="text-xs font-medium text-rose-600">{error}</p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-ink-400">{hint}</p>
      ) : null}
    </div>
  );
}

export function TextField({ label, error, hint, ...rest }: InputHTMLAttributes<HTMLInputElement> & {
  label: string; error?: string; hint?: string;
}) {
  return (
    <FieldShell label={label} error={error} hint={hint}>
      {({ id, describedBy, invalid }) => (
        <input id={id} aria-describedby={describedBy} aria-invalid={invalid}
          className={`field ${invalid ? "border-rose-500" : ""}`} {...rest} />
      )}
    </FieldShell>
  );
}

export function SelectField({ label, error, hint, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & {
  label: string; error?: string; hint?: string;
}) {
  return (
    <FieldShell label={label} error={error} hint={hint}>
      {({ id, describedBy, invalid }) => (
        <select id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field" {...rest}>
          {children}
        </select>
      )}
    </FieldShell>
  );
}

export function TextAreaField({ label, error, hint, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string; error?: string; hint?: string;
}) {
  return (
    <FieldShell label={label} error={error} hint={hint}>
      {({ id, describedBy, invalid }) => (
        <textarea id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field min-h-[88px]"
          {...rest} />
      )}
    </FieldShell>
  );
}

const statusTone: Record<string, string> = {
  CONFIRMED: "bg-signal-50 text-signal-700",
  CHECKED_IN: "bg-stay-50 text-stay-600",
  IN_SERVICE: "bg-amber-100 text-amber-600",
  COMPLETED: "bg-ink-100 text-ink-600",
  CHECKED_OUT: "bg-ink-100 text-ink-600",
  CANCELLED: "bg-ink-50 text-ink-400 line-through decoration-ink-300",
  NO_SHOW: "bg-rose-100 text-rose-600",
  OPEN: "bg-signal-50 text-signal-700",
  PAUSED: "bg-amber-100 text-amber-600",
};

export function StatusBadge({ status }: { status: BookingStatus | ReservationStatus | string }) {
  const label = status === "IN_SERVICE" ? "Your turn" : humanStatus(status);
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${statusTone[status]
      || "bg-ink-100 text-ink-600"}`}>{label}</span>
  );
}

export function SampleTag() {
  return (
    <span title="Demonstration listing, not a real business"
      className="inline-flex items-center rounded-md border border-dashed border-ink-300 px-1.5 py-0.5 text-[11px] font-medium text-ink-500">
      Sample
    </span>
  );
}

export function Modal({ open, title, onClose, children, footer, wide }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("input, select, textarea, button")?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink-950/40 sm:items-center sm:px-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId}
        className={`max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white p-6 shadow-xl sm:rounded-2xl ${wide ? "sm:max-w-2xl" : "sm:max-w-md"}`}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 id={titleId} className="text-lg font-semibold text-ink-900">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-md px-2 text-xl leading-none text-ink-400 hover:text-ink-700">×</button>
        </div>
        {children}
        {footer && <div className="mt-6 flex flex-wrap justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, items, label }: {
  value: T; onChange: (v: T) => void; items: { value: T; label: string; count?: number }[]; label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="mb-6 inline-flex rounded-xl bg-ink-50 p-1">
      {items.map((item) => (
        <button key={item.value} role="tab" aria-selected={value === item.value} onClick={() => onChange(item.value)}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${value === item.value
            ? "bg-white text-ink-900 shadow-sm" : "text-ink-500 hover:text-ink-800"}`}>
          {item.label}{item.count !== undefined && <span className="ml-1.5 text-ink-400">{item.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Metric({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="surface rounded-2xl px-4 py-3">
      <p className="text-xs text-ink-500">{label}</p>
      <p className="font-display mt-1 text-2xl font-semibold text-ink-900">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-ink-400">{hint}</p>}
    </div>
  );
}

export function DataTable<T>({ rows, columns, empty, rowKey }: {
  rows: T[]; rowKey: (row: T) => string; empty: ReactNode;
  columns: { header: string; cell: (row: T) => ReactNode; className?: string }[];
}) {
  if (!rows.length) return <>{empty}</>;
  return (
    <div className="surface overflow-x-auto rounded-2xl">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="border-b border-ink-100 bg-ink-50/60 text-xs text-ink-500">
          <tr>{columns.map((c) => <th key={c.header} scope="col" className={`px-4 py-3 font-medium ${c.className || ""}`}>{c.header}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-ink-100">
          {rows.map((row) => (
            <tr key={rowKey(row)} className="align-top">
              {columns.map((c) => <td key={c.header} className={`px-4 py-3 ${c.className || ""}`}>{c.cell(row)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-ink-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-200 border-t-ink-500" />
      {label}
    </span>
  );
}
