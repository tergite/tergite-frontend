import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { useMemo, Fragment } from "react";
import { Link, useLocation } from "react-router-dom";

export function TopbarBreadcrumb() {
  const location = useLocation();
  const pathParts = useMemo(
    () => location.pathname.split("/").filter((v) => v !== ""),
    [location.pathname]
  );
  return (
    <Breadcrumb className="hidden md:flex mr-auto">
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink asChild>
            <Link to="/">Dashboard</Link>
          </BreadcrumbLink>
        </BreadcrumbItem>
        {pathParts.map((part, idx, allParts) => (
          <Fragment key={idx}>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link to={`/${allParts.slice(0, idx + 1).join("/")}`}>
                  {part}
                </Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
          </Fragment>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
