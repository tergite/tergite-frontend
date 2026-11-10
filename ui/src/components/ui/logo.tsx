import { Link } from "react-router-dom";
import { LogoMark } from "./logo-mark";

export function Logo({ isExpanded = true }: Props) {
  return (
    <Link
      to="/"
      className="group flex h-[78px] shrink-0 items-center gap-3 border-b border-sidebar-highlight/10 px-5 text-left"
    >
      <span className="relative grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-sidebar-highlight/15 bg-sidebar-highlight/[0.06]">
        <LogoMark className="h-6 w-6" />
      </span>
      {isExpanded && (
        <span className="min-w-0">
          <span className="block font-display text-base font-semibold tracking-[0.12em] text-sidebar-highlight">
            WACQT
          </span>
          <span className="block text-[10px] font-medium uppercase tracking-[0.16em] text-sidebar-muted">
            Quantum computer
          </span>
          <span className="sr-only">
            WACQT: Wallenberg Centre for Quantum Technology
          </span>
        </span>
      )}
    </Link>
  );
}

interface Props {
  isExpanded?: boolean;
}
