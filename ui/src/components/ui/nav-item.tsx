import * as React from "react";
import { LucideProps } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

export function NavItem({
  to,
  isBig = false,
  Icon,
  text,
  isExpanded = true,
  children,
}: React.PropsWithChildren<Props>) {
  const location = useLocation();
  const colorsClass = React.useMemo(
    () =>
      location.pathname === to
        ? "bg-sidebar-highlight/[0.1] text-sidebar-highlight shadow-nav-active"
        : "text-sidebar-muted",
    [location.pathname, to]
  );

  const sizeClass = React.useMemo(() => {
    return isBig
      ? {
          icon: "font-medium h-5 w-5",
          text: "text-lg font-medium",
          gap: "gap-4",
        }
      : { icon: "h-4 w-4", text: "text-sm", gap: "gap-2" };
  }, [isBig]);

  const showText = isExpanded || Icon === undefined;

  return (
    <Link
      to={to}
      title={showText ? undefined : text}
      className={`flex h-10 px-3 items-center ${colorsClass} rounded-lg transition-all hover:bg-sidebar-highlight/[0.06] hover:text-sidebar-highlight`}
    >
      <div className={`flex ${sizeClass.gap} items-center`}>
        {Icon && (
          <Icon aria-label={Icon.displayName} className={sizeClass.icon} />
        )}
        {showText && <span className={sizeClass.text}>{text}</span>}
        <span className="sr-only">{text}</span>
        {children}
      </div>
    </Link>
  );
}

interface Props {
  to: string;
  text: string;
  isBig?: boolean;
  isExpanded?: boolean;
  Icon?: React.ForwardRefExoticComponent<
    Omit<LucideProps, "ref"> & React.RefAttributes<SVGSVGElement>
  >;
}
