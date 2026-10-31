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
        ? "bg-accent text-accent-foreground"
        : "text-muted-foreground",
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
      className={`flex h-9 px-2 items-center ${colorsClass} rounded-sm  transition-colors hover:text-foreground hover:bg-accent`}
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
