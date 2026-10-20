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
import { NoticeType } from "../../../../../../types";

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
  [NoticeType.PROJECT_ACCESS_REQUESTED]: {
    Icon: HelpingHand,
    label: "Access request",
    iconClassName: "text-primary",
    isActionable: true,
  },
  [NoticeType.PROJECT_ACCESS_APPROVED]: {
    Icon: CheckCircle2,
    label: "Access granted",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  [NoticeType.PROJECT_ACCESS_REJECTED]: {
    Icon: XCircle,
    label: "Access declined",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  [NoticeType.PROJECT_CREATE_REQUESTED]: {
    Icon: FolderPlus,
    label: "Project request",
    iconClassName: "text-primary",
    isActionable: true,
  },
  [NoticeType.PROJECT_CREATE_APPROVED]: {
    Icon: CheckCircle2,
    label: "Project created",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  [NoticeType.PROJECT_CREATE_REJECTED]: {
    Icon: XCircle,
    label: "Project declined",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  [NoticeType.PROJECT_CLOSE_REQUESTED]: {
    Icon: FolderX,
    label: "Closure request",
    iconClassName: "text-primary",
    isActionable: true,
  },
  [NoticeType.PROJECT_CLOSE_APPROVED]: {
    Icon: CheckCircle2,
    label: "Project closed",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  [NoticeType.PROJECT_CLOSE_REJECTED]: {
    Icon: XCircle,
    label: "Closure declined",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  [NoticeType.PROJECT_TRANSFER_REQUESTED]: {
    Icon: ArrowRightLeft,
    label: "Transfer request",
    iconClassName: "text-primary",
    isActionable: true,
  },
  [NoticeType.PROJECT_TRANSFER_APPROVED]: {
    Icon: CheckCircle2,
    label: "Project transferred",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  [NoticeType.PROJECT_TRANSFER_REJECTED]: {
    Icon: XCircle,
    label: "Transfer declined",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  [NoticeType.QPU_SECONDS_REQUESTED]: {
    Icon: Clock,
    label: "QPU time request",
    iconClassName: "text-primary",
    isActionable: true,
  },
  [NoticeType.QPU_SECONDS_GRANTED]: {
    Icon: CheckCircle2,
    label: "QPU time granted",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  [NoticeType.QPU_SECONDS_DENIED]: {
    Icon: XCircle,
    label: "QPU time declined",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  [NoticeType.QPU_SECONDS_LOW]: {
    Icon: BatteryLow,
    label: "QPU time low",
    iconClassName: "text-amber-600",
    isActionable: false,
  },
  [NoticeType.QPU_SECONDS_DEPLETED]: {
    Icon: BatteryWarning,
    label: "QPU time exhausted",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  [NoticeType.PROJECT_MEMBERSHIP_GRANTED]: {
    Icon: UserPlus,
    label: "Added to project",
    iconClassName: "text-green-600",
    isActionable: false,
  },
  [NoticeType.PROJECT_MEMBERSHIP_REVOKED]: {
    Icon: UserMinus,
    label: "Removed from project",
    iconClassName: "text-destructive",
    isActionable: false,
  },
  [NoticeType.PROJECT_ADMIN_ASSIGNED]: {
    Icon: UserCog,
    label: "Made project admin",
    iconClassName: "text-primary",
    isActionable: false,
  },
  [NoticeType.CUSTOM]: {
    Icon: Megaphone,
    label: "Announcement",
    iconClassName: "text-primary",
    isActionable: false,
  },
  [NoticeType.CUSTOM_BROADCAST]: {
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
