import type { ReactNode } from "react";

type Props = {
  title?: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function DashboardCard({ title, eyebrow, action, children, className = "" }: Props) {
  return (
    <section className={`glass-panel min-w-0 rounded-lg p-5 ${className}`}>
      {(title || eyebrow || action) && (
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            {eyebrow && <p className="mb-1 text-[11px] font-semibold uppercase text-studio-violet">{eyebrow}</p>}
            {title && <h2 className="text-base font-semibold text-studio-ink">{title}</h2>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
