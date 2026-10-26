import {
  ArrowRightLeft,
  BatteryLow,
  BatteryWarning,
  BellRing,
  CheckCircle2,
  Clock,
  FolderPlus,
  FolderX,
  HelpingHand,
  Megaphone,
  UserCog,
  UserMinus,
  UserPlus,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { type NoticeType } from "@/lib/api/types";

interface NotificationMeta {
  Icon: LucideIcon;
  label: string;
  // tailwind text colour token for the icon
  iconClassName: string;
  // whether the recipient can act on it, which earns the accent border
  isActionable: boolean;
}

/**
 * Per-type icon, label and colour.
 *
 * Kept in one map so the bell, the list item and any future surface agree, rather
 * than each re-deriving the look from the type.
 */
export const NOTIFICATION_TYPE_META: Record<NoticeType, NotificationMeta> = {
  "project-access-requested": {
    Icon: HelpingHand,
    label: "Access request",
    iconClassName: "text-primary",
    isActionable: true,
  },
  "project-access-approved": {
    Icon: CheckCircle2,
    label: "Access granted",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  "project-access-rejected": {
    Icon: XCircle,
    label: "Access declined",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  "project-create-requested": {
    Icon: FolderPlus,
    label: "Project request",
    iconClassName: "text-primary",
    isActionable: true,
  },
  "project-create-approved": {
    Icon: CheckCircle2,
    label: "Project created",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  "project-create-rejected": {
    Icon: XCircle,
    label: "Project declined",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  "project-close-requested": {
    Icon: FolderX,
    label: "Closure request",
    iconClassName: "text-primary",
    isActionable: true,
  },
  "project-close-approved": {
    Icon: CheckCircle2,
    label: "Project closed",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  "project-close-rejected": {
    Icon: XCircle,
    label: "Closure declined",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  "project-transfer-requested": {
    Icon: ArrowRightLeft,
    label: "Transfer request",
    iconClassName: "text-primary",
    isActionable: true,
  },
  "project-transfer-approved": {
    Icon: CheckCircle2,
    label: "Project transferred",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  "project-transfer-rejected": {
    Icon: XCircle,
    label: "Transfer declined",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  "qpu-seconds-requested": {
    Icon: Clock,
    label: "QPU time request",
    iconClassName: "text-primary",
    isActionable: true,
  },
  "qpu-seconds-granted": {
    Icon: CheckCircle2,
    label: "QPU time granted",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  "qpu-seconds-denied": {
    Icon: XCircle,
    label: "QPU time declined",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  "qpu-seconds-low": {
    Icon: BatteryLow,
    label: "QPU time low",
    iconClassName: "text-amber-600",
    isActionable: false,
  },
  "qpu-seconds-depleted": {
    Icon: BatteryWarning,
    label: "QPU time exhausted",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  "project-membership-granted": {
    Icon: UserPlus,
    label: "Added to project",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  "project-membership-revoked": {
    Icon: UserMinus,
    label: "Removed from project",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  "project-admin-assigned": {
    Icon: UserCog,
    label: "Made project admin",
    iconClassName: "text-primary",
    isActionable: false,
  },
  "custom": {
    Icon: Megaphone,
    label: "Announcement",
    iconClassName: "text-primary",
    isActionable: false,
  },
  "custom-broadcast": {
    Icon: Megaphone,
    label: "Announcement to all",
    iconClassName: "text-primary",
    isActionable: false,
  },
};

export const FALLBACK_NOTIFICATION_META: NotificationMeta = {
  Icon: BellRing,
  label: "Notification",
  iconClassName: "text-muted-foreground",
  isActionable: false,
};

/**
 * The look for a notification type, falling back for a type this build does not know.
 *
 * A newer MSS can emit a type this dashboard has never heard of; showing it plainly
 * beats dropping it or crashing the bell.
 *
 * @param type - the notification type as returned by the API
 */
export function getNotificationMeta(type: NoticeType): NotificationMeta {
  return NOTIFICATION_TYPE_META[type] ?? FALLBACK_NOTIFICATION_META;
}
