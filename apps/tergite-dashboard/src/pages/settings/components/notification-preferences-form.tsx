import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  notificationPreferencesQuery,
  updateNotificationPreferences,
} from "@/lib/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { NotificationType, type ChannelPrefs } from "../../../../types";
import { getNotificationMeta } from "@/components/layouts/dashboard/components/notifications/meta";

// in the order they matter to a user: things awaiting them, then outcomes
const ORDERED_TYPES: NotificationType[] = [
  NotificationType.PROJECT_ACCESS_REQUESTED,
  NotificationType.QPU_SECONDS_REQUESTED,
  NotificationType.PROJECT_ACCESS_APPROVED,
  NotificationType.PROJECT_ACCESS_REJECTED,
  NotificationType.QPU_SECONDS_GRANTED,
  NotificationType.QPU_SECONDS_DENIED,
  NotificationType.QPU_SECONDS_LOW,
  NotificationType.QPU_SECONDS_DEPLETED,
  NotificationType.PROJECT_MEMBERSHIP_REVOKED,
];

export function NotificationPreferencesForm() {
  const queryClient = useQueryClient();
  const { data: prefs } = useQuery(notificationPreferencesQuery());

  const update = useMutation({
    mutationFn: updateNotificationPreferences,
    // the response is the full, server-resolved set, so trust it over the toggle
    onSuccess: (data) =>
      queryClient.setQueryData(notificationPreferencesQuery().queryKey, data),
    throwOnError: true,
  });

  const handleChange = useCallback(
    (type: NotificationType, prev: ChannelPrefs, isEmailOn: boolean) =>
      update.mutate({ [type]: { ...prev, email: isEmailOn } }),
    [update],
  );

  if (!prefs) {
    return null;
  }

  return (
    <ul className="grid gap-5">
      {ORDERED_TYPES.map((type) => {
        const { Icon, label, iconClassName } = getNotificationMeta(type);
        const pref = prefs[type];
        if (!pref) {
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
              checked={pref.email}
              disabled={update.isPending}
              onCheckedChange={(isOn) => handleChange(type, pref, isOn)}
            />
          </li>
        );
      })}
    </ul>
  );
}
