import type { ReactNode } from "react";

interface Props {
  title?: string;
  eyebrow?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function Card({ title, eyebrow, action, className = "", children }: Props) {
  return (
    <section className={`glass animate-fade-in-up p-5 sm:p-6 ${className}`}>
      {(title || eyebrow || action) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            {title && <h3 className="mt-1 font-display text-lg font-semibold">{title}</h3>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}
