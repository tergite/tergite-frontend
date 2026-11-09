import { cn } from "@/lib/utils";

/**
 * The Tergite favicon's rings and cross, in the sidebar's colours, for dark backgrounds.
 */
export function LogoMark({ className }: Props) {
  return (
    <svg
      viewBox="0 0 206 206"
      fill="none"
      aria-hidden="true"
      className={cn("text-sidebar-highlight", className)}
    >
      <circle cx="103" cy="103" r="96.5" strokeWidth="13" className="stroke-sidebar-primary" />
      <circle cx="103" cy="102" r="79.5" strokeWidth="7" className="stroke-sidebar-ring" />
      <circle cx="103" cy="101" r="66.5" strokeWidth="5" className="stroke-sidebar-ring/60" />
      <g stroke="currentColor">
        <path d="M103 166V156" strokeWidth="9" />
        <path d="M103 44V34" strokeWidth="9" />
        <path d="M97 154V109M109 154V109M96 152H111" strokeWidth="5" />
        <path d="M152 109H107M152 97H107M150 110V95" strokeWidth="5" />
        <path d="M54 97H99M54 109H99M56 95V110" strokeWidth="5" />
        <path d="M109 54V99M97 54V99M110 56H95" strokeWidth="5" />
        <path d="M118.5 43V64M87.5 43V64" strokeWidth="7" />
        <path d="M119.5 46H87.5" strokeWidth="6" />
      </g>
      <rect x="97" y="55" width="12" height="95" fill="currentColor" />
      <rect x="54" y="97" width="95" height="12" fill="currentColor" />
    </svg>
  );
}

interface Props {
  className?: string;
}
