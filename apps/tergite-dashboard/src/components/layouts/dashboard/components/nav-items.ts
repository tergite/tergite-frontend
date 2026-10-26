import {
  ClipboardList,
  Cpu,
  FolderKanban,
  HardHat,
  HelpingHand,
  Home,
  KeyRound,
  KeySquare,
  Settings2,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";

// the sidebar and the mobile menu both render these; a group without a title is not folded
export const NAV_GROUPS: NavGroup[] = [
  {
    name: "main",
    links: [
      { to: "/", text: "Dashboard", Icon: Home },
      { to: "/devices", text: "Devices", Icon: Cpu },
    ],
  },
  {
    name: "access",
    title: "Access",
    Icon: KeyRound,
    links: [
      { to: "/projects", text: "Projects", Icon: FolderKanban },
      { to: "/tokens", text: "Tokens", Icon: KeySquare },
      { to: "/requests", text: "Requests", Icon: ClipboardList },
    ],
  },
  {
    name: "admin",
    title: "Admin",
    Icon: Settings2,
    isAdminOnly: true,
    links: [
      {
        to: "/admin-requests",
        text: "Requests",
        Icon: HelpingHand,
        shouldShowPendingCount: true,
      },
      { to: "/admin-projects", text: "Projects", Icon: HardHat },
      { to: "/admin-control", text: "Control", Icon: SlidersHorizontal },
    ],
  },
];

export type NavGroup = {
  name: string;
  title?: string;
  Icon?: LucideIcon;
  isAdminOnly?: boolean;
  links: NavLink[];
};

export type NavLink = {
  to: string;
  text: string;
  Icon: LucideIcon;
  shouldShowPendingCount?: boolean;
};
