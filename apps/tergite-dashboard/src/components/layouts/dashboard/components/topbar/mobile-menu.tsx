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

export function MobileMenu({ pendingRequestsCount, isUserAdmin }: Props) {
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
        className="sm:max-w-xs"
      >
        <SheetTitle>
          <Logo />
        </SheetTitle>

        <nav className="grid gap-4 text-lg font-medium overflow-y-auto max-h-[75vh]">
          {NAV_GROUPS.filter(
            (group) => isUserAdmin || !group.isAdminOnly
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
          className={`flex text-lg font-medium gap-4 h-9 px-2 justify-start rounded-sm transition-colors text-muted-foreground active:text-accent-foreground hover:text-foreground w-full`}
        >
          <group.Icon className="h-5 w-5 font-medium" />
          {group.title}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="flex flex-col gap-6 my-6 ml-4 -mr-4">
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
  isUserAdmin: boolean;
}
