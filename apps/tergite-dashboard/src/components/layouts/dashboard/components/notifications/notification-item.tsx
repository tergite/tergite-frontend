import { Button } from "@/components/ui/button";
import { cn, toRelative } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DateTime } from "luxon";
import { useCallback } from "react";
import { Notification } from "types";
import {
  approveMyRequest,
  rejectMyRequest,
  refreshMyNotifications,
  refreshMyRequests,
  refreshMyProjectsQueries,
  setNotificationRead,
} from "@/lib/api-client";
import { ReloadIcon } from "@radix-ui/react-icons";
import { getNotificationMeta } from "./meta";

export function NotificationItem({ notification }: Props) {
  const queryClient = useQueryClient();
  const { Icon, label, iconClassName, isActionable } = getNotificationMeta(
    notification.type,
  );
  const isUnread = !notification.read_at;
  const requestId = notification.action?.request_id;
  const canAct = isActionable && !!requestId;

  const refreshAll = useCallback(async () => {
    await refreshMyNotifications(queryClient);
    await refreshMyRequests(queryClient);
    await refreshMyProjectsQueries(queryClient);
  }, [queryClient]);

  const approval = useMutation({
    mutationFn: approveMyRequest,
    onSuccess: refreshAll,
    throwOnError: true,
  });

  const rejection = useMutation({
    mutationFn: rejectMyRequest,
    onSuccess: refreshAll,
    throwOnError: true,
  });

  const readToggle = useMutation({
    mutationFn: setNotificationRead,
    onSuccess: async () => await refreshMyNotifications(queryClient),
    throwOnError: true,
  });

  const isPending = approval.isPending || rejection.isPending;

  return (
    <li
      data-cy-notification={notification.type}
      data-cy-unread={isUnread}
      className={cn(
        "flex gap-3 px-4 py-3 text-sm border-b last:border-b-0",
        // an accent border marks the ones the reader can do something about
        canAct && "border-l-2 border-l-primary",
        isUnread && "bg-muted/50",
      )}
    >
      <Icon className={cn("h-4 w-4 mt-0.5 shrink-0", iconClassName)} />
      <div className="grid gap-1 w-full">
        <div className="flex items-start justify-between gap-2">
          <span className="font-medium">{notification.title}</span>
          <span className="text-xs text-muted-foreground shrink-0">
            {toRelative(DateTime.fromISO(notification.created_at))}
          </span>
        </div>
        <span className="text-muted-foreground">{notification.body}</span>
        <span className="text-xs text-muted-foreground">{label}</span>

        {canAct && (
          <div className="grid grid-cols-2 gap-2 mt-2">
            <Button
              type="button"
              size="sm"
              onClick={() => approval.mutate(requestId)}
              disabled={isPending}
            >
              {approval.isPending && (
                <ReloadIcon className="mr-2 h-3 w-3 animate-spin" />
              )}
              Approve
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="text-destructive border-destructive"
              onClick={() => rejection.mutate({ id: requestId })}
              disabled={isPending}
            >
              {rejection.isPending && (
                <ReloadIcon className="mr-2 h-3 w-3 animate-spin" />
              )}
              Reject
            </Button>
          </div>
        )}

        {isUnread && (
          <button
            type="button"
            data-cy-mark-read
            className="text-xs text-left underline text-muted-foreground w-fit"
            onClick={() =>
              readToggle.mutate({ id: notification.id, isRead: true })
            }
          >
            Mark as read
          </button>
        )}
      </div>
    </li>
  );
}

interface Props {
  notification: Notification;
}
