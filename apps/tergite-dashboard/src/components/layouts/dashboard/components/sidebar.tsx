import {
  PanelLeftClose,
  PanelRightClose,
  ChevronDown,
  ChevronRight,
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

export function Sidebar({
  isExpanded,
  onIsExpandedChange,
  isAdmin,
  pendingRequestsCount,
  personalProject,
}: Props) {
  const widthClass = isExpanded ? "w-56" : "w-18";

  return (
    <aside
      data-testid="sidebar"
      className={`fixed inset-y-0 left-0 z-10 hidden sm:pt-1 ${widthClass} flex-col border-r bg-background sm:flex`}
    >
      <Logo isExpanded={isExpanded} />
      <nav className="flex flex-col gap-4 px-6 sm:py-4 overflow-y-auto max-h-[75vh]">
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

      <div className="mt-auto grid gap-3 justify-items-center py-4">
        <QpuMeter project={personalProject} isExpanded={isExpanded} />
        {/* the toggle keeps its own wrapper: tests click the button's parent */}
        <div className="mx-auto">
          {isExpanded && (
            <IconButton
              variant="outline"
              Icon={PanelLeftClose}
              onClick={() => onIsExpandedChange()}
            />
          )}
          {!isExpanded && (
            <IconButton
              variant="outline"
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
          className={`flex text-sm gap-2 h-9 px-2 justify-start rounded-sm  transition-colors text-muted-foreground active:text-accent-foreground hover:text-foreground w-full`}
        >
          <group.Icon className="h-4 w-4" />
          {isExpanded ? <span>{group.title}</span> : null}
          {isExpanded && !isOpen && <ChevronRight className="ml-auto h-4 w-4" />}
          {isExpanded && isOpen && <ChevronDown className="ml-auto h-4 w-4" />}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent
        className={`flex flex-col gap-4 my-2 border-l ${isExpanded ? "ml-4" : ""}`}
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
