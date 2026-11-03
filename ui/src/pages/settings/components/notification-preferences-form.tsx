import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  noticePreferencesQuery,
  updateNoticePreferences,
} from "@/lib/api/notices";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import type { NoticeType } from "@/lib/api/types";
import {
  getNotificationMeta,
} from "@/components/layouts/dashboard/components/notifications/notice-type-styles";

// in the order they matter to a user: things awaiting them, then outcomes
const ORDERED_TYPES: NoticeType[] = [
  "project-access-requested",
  "qpu-seconds-requested",
  "pulse-access-requested",
  "project-create-requested",
  "project-close-requested",
  "project-transfer-requested",
  "project-access-approved",
  "project-access-rejected",
  "qpu-seconds-granted",
  "qpu-seconds-denied",
  "pulse-access-granted",
  "pulse-access-denied",
  "project-create-approved",
  "project-create-rejected",
  "project-close-approved",
  "project-close-rejected",
  "project-transfer-approved",
  "project-transfer-rejected",
  "qpu-seconds-low",
  "qpu-seconds-depleted",
  "project-membership-granted",
  "project-membership-revoked",
  "project-admin-assigned",
  "custom",
  "custom-broadcast",
];

export function NotificationPreferencesForm() {
  const queryClient = useQueryClient();
  const { data: prefs } = useQuery(noticePreferencesQuery);

  const update = useMutation({
    mutationFn: updateNoticePreferences,
    // the response is the full, server-resolved set, so trust it over the toggle
    onSuccess: (data) =>
      queryClient.setQueryData(noticePreferencesQuery.queryKey, data),
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
