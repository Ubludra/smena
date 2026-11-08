import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  busy?: boolean;
  children: ReactNode;
}

/**
 * Base button everywhere in the app. `busy` disables the control and shows a
 * spinner — submit buttons must use it (product rule §29: no double submits,
 * no success shown while the server call is in flight).
 */
export function Button({
  variant = "primary",
  busy = false,
  children,
  disabled,
  className = "",
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      className={`btn btn-${variant}${busy ? " btn-busy" : ""} ${className}`}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    >
      {busy && <span className="spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}
