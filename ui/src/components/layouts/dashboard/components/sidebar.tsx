import {
  PanelLeftClose,
  PanelRightClose,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { Logo } from "@/components/ui/logo";
import { Button, IconButton } from "@/components/ui/button";
import { useState } from "react";
import { Collapsible, CollapsibleTrigger } from "@/components/ui/collapsible";
import { CollapsibleContent } from "@radix-ui/react-collapsible";
import { NavItem } from "@/components/ui/nav-item";
import { Badge } from "@/components/ui/badge";
import type { Project } from "@/lib/api/types";
import { QpuMeter } from "./qpu-meter";
import { NAV_GROUPS, type NavGroup } from "./nav-items";

// the year and month of the release, as its version is year.month.patch
const RELEASE = import.meta.env.VITE_APP_VERSION.split(".").slice(0, 2).join(".");

export function Sidebar({
  isExpanded,
  onIsExpandedChange,
  isAdmin,
  pendingRequestsCount,
  personalProject,
}: Props) {
  const widthClass = isExpanded ? "w-60" : "w-20";

  return (
    <aside
      data-testid="sidebar"
      className={`fixed inset-y-0 left-0 z-40 hidden ${widthClass} flex-col border-r border-sidebar-highlight/10 bg-sidebar text-sidebar-foreground shadow-sidebar transition-[width] duration-300 sm:flex`}
    >
      <Logo isExpanded={isExpanded} />
      <nav className="flex max-h-[75vh] flex-col gap-5 overflow-y-auto px-4 py-6">
        {NAV_GROUPS.filter((group) => isAdmin || !group.isAdminOnly).map(
          (group) => (
            <SidebarGroup
              key={group.name}
              group={group}
              isExpanded={isExpanded}
              pendingRequestsCount={pendingRequestsCount}
            />
          )
        )}
      </nav>

      <p
        data-cy-release
        title={`Release ${import.meta.env.VITE_APP_VERSION}`}
        className={`mt-auto flex items-center gap-1.5 pb-3 text-[10px] font-medium uppercase tracking-[0.16em] text-sidebar-subtle ${isExpanded ? "px-7" : "justify-center"}`}
      >
        {isExpanded && <Sparkles className="h-3 w-3 shrink-0" />}
        {isExpanded ? `Release ${RELEASE}` : RELEASE}
      </p>
      <div className="grid justify-items-center gap-4 border-t border-sidebar-highlight/10 py-5 text-sidebar-soft">
        <QpuMeter project={personalProject} isExpanded={isExpanded} />
        {/* the toggle keeps its own wrapper: tests click the button's parent */}
        <div className="mx-auto">
          {isExpanded && (
            <IconButton
              variant="ghost"
              className="text-sidebar-muted hover:bg-sidebar-highlight/10 hover:text-sidebar-highlight"
              Icon={PanelLeftClose}
              onClick={() => onIsExpandedChange()}
            />
          )}
          {!isExpanded && (
            <IconButton
              variant="ghost"
              className="text-sidebar-muted hover:bg-sidebar-highlight/10 hover:text-sidebar-highlight"
              Icon={PanelRightClose}
              onClick={() => onIsExpandedChange()}
            />
          )}
        </div>
      </div>
    </aside>
  );
}

function SidebarGroup({ group, isExpanded, pendingRequestsCount }: GroupProps) {
  const [isOpen, setIsOpen] = useState(true);
  const links = group.links.map(({ to, text, Icon, shouldShowPendingCount }) => (
    <NavItem key={to} to={to} Icon={Icon} isExpanded={isExpanded} text={text}>
      {shouldShowPendingCount && " "}
      {shouldShowPendingCount && !!pendingRequestsCount && isExpanded && (
        <Badge variant="default">{pendingRequestsCount}</Badge>
      )}
    </NavItem>
  ));
  if (!group.title || !group.Icon) return <>{links}</>;

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className="w-full"
      data-testid={`${group.name}-submenu`}
    >
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          className="flex h-8 w-full justify-start gap-2 px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-sidebar-subtle hover:bg-sidebar-highlight/[0.04] hover:text-sidebar-soft"
        >
          <group.Icon className="h-4 w-4" />
          {isExpanded ? <span>{group.title}</span> : null}
          {isExpanded && !isOpen && <ChevronRight className="ml-auto h-4 w-4" />}
          {isExpanded && isOpen && <ChevronDown className="ml-auto h-4 w-4" />}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent
        className={`my-2 flex flex-col gap-1 ${isExpanded ? "ml-1" : ""}`}
      >
        {links}
      </CollapsibleContent>
    </Collapsible>
  );
}

interface GroupProps {
  group: NavGroup;
  isExpanded: boolean;
  pendingRequestsCount: number;
}

interface Props {
  isExpanded: boolean;
  onIsExpandedChange: () => void;
  pendingRequestsCount: number;
  isAdmin: boolean;
  personalProject?: Project;
}
