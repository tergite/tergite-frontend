import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  noticePreferencesQuery,
  updateNoticePreferences,
} from "@/lib/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { NoticeType } from "../../../../types";
import { getNotificationMeta } from "@/components/layouts/dashboard/components/notifications/meta";

// in the order they matter to a user: things awaiting them, then outcomes
const ORDERED_TYPES: NoticeType[] = [
  NoticeType.PROJECT_ACCESS_REQUESTED,
  NoticeType.QPU_SECONDS_REQUESTED,
  NoticeType.PROJECT_CREATE_REQUESTED,
  NoticeType.PROJECT_CLOSE_REQUESTED,
  NoticeType.PROJECT_TRANSFER_REQUESTED,
  NoticeType.PROJECT_ACCESS_APPROVED,
  NoticeType.PROJECT_ACCESS_REJECTED,
  NoticeType.QPU_SECONDS_GRANTED,
  NoticeType.QPU_SECONDS_DENIED,
  NoticeType.PROJECT_CREATE_APPROVED,
  NoticeType.PROJECT_CREATE_REJECTED,
  NoticeType.PROJECT_CLOSE_APPROVED,
  NoticeType.PROJECT_CLOSE_REJECTED,
  NoticeType.PROJECT_TRANSFER_APPROVED,
  NoticeType.PROJECT_TRANSFER_REJECTED,
  NoticeType.QPU_SECONDS_LOW,
  NoticeType.QPU_SECONDS_DEPLETED,
  NoticeType.PROJECT_MEMBERSHIP_GRANTED,
  NoticeType.PROJECT_MEMBERSHIP_REVOKED,
  NoticeType.PROJECT_ADMIN_ASSIGNED,
  NoticeType.CUSTOM,
  NoticeType.CUSTOM_BROADCAST,
];

export function NotificationPreferencesForm() {
  const queryClient = useQueryClient();
  const { data: prefs } = useQuery(noticePreferencesQuery());

  const update = useMutation({
    mutationFn: updateNoticePreferences,
    // the response is the full, server-resolved set, so trust it over the toggle
    onSuccess: (data) =>
      queryClient.setQueryData(noticePreferencesQuery().queryKey, data),
    throwOnError: true,
  });

  const handleChange = useCallback(
    (type: NoticeType, isEmailOn: boolean) =>
      update.mutate({ [type]: isEmailOn }),
    [update],
  );

  if (!prefs) {
    return null;
  }

  return (
    <ul className="grid gap-5">
      {ORDERED_TYPES.map((type) => {
        const { Icon, label, iconClassName } = getNotificationMeta(type);
        const isEmailOn = prefs[type];
        if (isEmailOn === undefined) {
          return null;
        }

        return (
          <li key={type} className="flex items-center gap-3">
            <Icon className={`h-4 w-4 shrink-0 ${iconClassName}`} />
            <Label htmlFor={`email-${type}`} className="mr-auto font-normal">
              {label}
            </Label>
            <Switch
              id={`email-${type}`}
              data-cy-email-switch={type}
              aria-label={`Email me about ${label}`}
              checked={isEmailOn}
              disabled={update.isPending}
              onCheckedChange={(isOn) => handleChange(type, isOn)}
            />
          </li>
        );
      })}
    </ul>
  );
}
