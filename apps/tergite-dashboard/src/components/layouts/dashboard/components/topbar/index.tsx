import { UserRound } from "lucide-react";
import { Button, IconButton } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { type Project, type User } from "../../../../../../types";
import { Link } from "react-router-dom";

import { MobileMenu } from "./mobile-menu";
import { TopbarBreadcrumb } from "./breadcrumb";
import { useState } from "react";
import { DarkToggleBtn } from "@/components/ui/dark-toggle-btn";

export function Topbar({
  currentProject = "",
  currentUser,
  onProjectChange,
  projects,
  onLogout,
  pendingRequestsTotal,
  isUserAdmin,
}: TopbarProps) {
  const username = currentUser?.email?.split("@")[0];
  const [selectKey, setSelectKey] = useState(+new Date());

  return (
    <header
      data-testid="topbar"
      className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b bg-background px-4 sm:static sm:h-auto sm:border-0 sm:bg-transparent sm:px-6"
    >
      <MobileMenu
        pendingRequestsCount={pendingRequestsTotal}
        isUserAdmin={isUserAdmin}
      />

      <TopbarBreadcrumb />
      <DarkToggleBtn className="ml-auto" />
      <Select
        key={selectKey}
        data-testid="project-select"
        value={currentProject}
        onValueChange={onProjectChange}
      >
        <SelectTrigger className="w-fit">
          <span className="hidden sm:inline text-muted-foreground pr-1">
            Project:{" "}
          </span>
          <SelectValue placeholder="Select project" />
        </SelectTrigger>
        <SelectContent id="project-selector">
          <Button
            role="option"
            className="w-full px-2 justify-start text-muted-foreground"
            variant="ghost"
            onClick={(e) => {
              e.stopPropagation();
              onProjectChange(undefined);
              // to make sure the select element re-renders
              setSelectKey(+new Date());
            }}
          >
            None
          </Button>
          {projects.map((project) => (
            <SelectItem value={project.id} key={project.id}>
              {project.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <IconButton
            variant="outline"
            className="rounded-full overflow-hidden focus:mr-[1px]"
            Icon={UserRound}
          />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>{username}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link to="/settings" data-cy-settings-link>
              Settings
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />

          <DropdownMenuItem onClick={onLogout}>Logout</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}

interface TopbarProps {
  currentProject?: string;
  currentUser: User;
  projects: Project[];
  onProjectChange: (projectId?: string) => void;
  onLogout: () => void;
  pendingRequestsTotal: number;
  isUserAdmin: boolean;
}
