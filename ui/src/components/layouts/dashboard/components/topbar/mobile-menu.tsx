import { Logo } from "@/components/ui/logo";
import { NavItem } from "@/components/ui/nav-item";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetTitle,
} from "@/components/ui/sheet";
import { PanelLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { NAV_GROUPS, type NavGroup } from "../nav-items";

export function MobileMenu({ pendingRequestsCount, isAdmin }: Props) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button size="icon" variant="outline" className="sm:hidden">
          <PanelLeft className="h-5 w-5" />
          <span className="sr-only">Toggle Menu</span>
        </Button>
      </SheetTrigger>
      <SheetContent
        data-testid="mobile-menu"
        side="left"
        className="border-sidebar-highlight/10 bg-sidebar p-0 text-sidebar-foreground sm:max-w-xs"
      >
        <SheetTitle>
          <Logo />
        </SheetTitle>

        <nav className="grid max-h-[75vh] gap-4 overflow-y-auto px-4 py-6 text-lg font-medium">
          {NAV_GROUPS.filter(
            (group) => isAdmin || !group.isAdminOnly
          ).map((group) => (
            <MobileMenuGroup
              key={group.name}
              group={group}
              pendingRequestsCount={pendingRequestsCount}
            />
          ))}
        </nav>
      </SheetContent>
    </Sheet>
  );
}

function MobileMenuGroup({ group, pendingRequestsCount }: GroupProps) {
  const [isOpen, setIsOpen] = useState(true);
  const links = group.links.map(({ to, text, Icon, shouldShowPendingCount }) => (
    <NavItem key={to} to={to} Icon={Icon} isBig={true} text={text}>
      {shouldShowPendingCount && !!pendingRequestsCount && (
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
          className="flex h-9 w-full justify-start gap-4 px-3 text-sm font-semibold uppercase tracking-[0.14em] text-sidebar-subtle hover:bg-sidebar-highlight/[0.04] hover:text-sidebar-soft"
        >
          <group.Icon className="h-5 w-5 font-medium" />
          {group.title}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="my-2 flex flex-col gap-1">
        {links}
      </CollapsibleContent>
    </Collapsible>
  );
}

interface GroupProps {
  group: NavGroup;
  pendingRequestsCount: number;
}

interface Props {
  pendingRequestsCount: number;
  isAdmin: boolean;
}
