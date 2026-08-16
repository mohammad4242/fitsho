import type { ReactNode } from "react";

export type AdminAccordionSectionControl = {
  id: string;
  title: string;
  isOpen: boolean;
  onToggle: () => void;
};

type AdminAccordionSectionProps = AdminAccordionSectionControl & {
  children: ReactNode;
};

export function AdminAccordionSection({
  id,
  title,
  isOpen,
  onToggle,
  children,
}: AdminAccordionSectionProps) {
  const panelId = `admin-exercise-section-${id}`;

  return (
    <section className="admin-form-section admin-accordion-section" data-expanded={isOpen}>
      <header className="admin-form-section__header">
        <button
          aria-controls={panelId}
          aria-expanded={isOpen}
          className="admin-form-section__trigger"
          onClick={onToggle}
          type="button"
        >
          <span>{title}</span>
          <span aria-hidden="true" className="admin-form-section__icon">
            {isOpen ? "⌃" : "⌄"}
          </span>
        </button>
      </header>
      {isOpen && <div className="admin-form-section__panel" id={panelId}>{children}</div>}
    </section>
  );
}
