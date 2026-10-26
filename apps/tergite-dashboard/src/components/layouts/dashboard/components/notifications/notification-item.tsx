import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatRelative } from "@/lib/time";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DateTime } from "luxon";
import { useCallback } from "react";
import { type Notice } from "@/lib/api/types";
import {
  approveMyRequest,
  refreshDecisionQueries,
  rejectMyRequest,
} from "@/lib/api/requests";
import { dismissNotice, refreshMyNotices } from "@/lib/api/notices";
import { ReloadIcon } from "@radix-ui/react-icons";
import { getNotificationMeta } from "./notice-type-styles";

export function NotificationItem({ notice }: Props) {
  const queryClient = useQueryClient();
  const { Icon, label, iconClassName, isActionable } = getNotificationMeta(
    notice.type,
  );
  // what can be acted on are the prompts to decide a request, which they refer to
  const requestId = isActionable ? notice.ref_id : undefined;
  const canAct = isActionable && !!requestId;

  const refreshAll = useCallback(async () => {
    await refreshDecisionQueries(queryClient);
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

  const dismissal = useMutation({
    mutationFn: dismissNotice,
    onSuccess: async () => await refreshMyNotices(queryClient),
    throwOnError: true,
  });

  const isPending = approval.isPending || rejection.isPending;

  return (
    <li
      data-cy-notification={notice.type}
      className={cn(
        "flex gap-3 px-4 py-3 text-sm border-b last:border-b-0 bg-muted/50",
        // an accent border marks the ones the reader can do something about
        canAct && "border-l-2 border-l-primary",
      )}
    >
      <Icon className={cn("h-4 w-4 mt-0.5 shrink-0", iconClassName)} />
      <div className="grid gap-1 w-full">
        <div className="flex items-start justify-between gap-2">
          <span className="font-medium">{notice.title}</span>
          <span className="text-xs text-muted-foreground shrink-0">
            {formatRelative(DateTime.fromISO(notice.created_at))}
          </span>
        </div>
        <span className="text-muted-foreground">{notice.body}</span>
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

        <button
          type="button"
          data-cy-mark-read
          className="text-xs text-left underline text-muted-foreground w-fit"
          onClick={() => dismissal.mutate(notice.id)}
          disabled={dismissal.isPending}
        >
          Mark as read
        </button>
      </div>
    </li>
  );
}

interface Props {
  // one of the reader's unread notices, as the bell lists no others
  notice: Notice;
}
