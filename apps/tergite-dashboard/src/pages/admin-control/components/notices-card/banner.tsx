import { IconButton } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import {
  deleteNotice,
  refreshAllNoticeCounts,
  refreshAllNotices,
} from "@/lib/api/notices";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { DateTime } from "luxon";
import { useMemo } from "react";
import { SEVERITY_LABELS } from "@/components/ui/notice-banner";
import { type NoticeSeverity, type Notice } from "@/lib/api/types";

const SEVERITY_BADGE_CLASSES: Record<NoticeSeverity, string> = {
  3:
    "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  2:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  1:
    "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

export function AdminNoticeBanner({ notice }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const severityClass = SEVERITY_BADGE_CLASSES[notice.severity];
  const title = useMemo(
    () => (notice.user_id ? "" : " · All users"),
    [notice.user_id],
  );

  const noticeDeletion = useMutation({
    mutationKey: ["admin", "notices", "delete", notice.id],
    async mutationFn(id: string) {
      return await deleteNotice(id);
    },
    async onSuccess() {
      await refreshAllNotices(queryClient);
      await refreshAllNoticeCounts(queryClient);
      toast({ title: "Notice deleted" });
    },
    throwOnError: true,
  });

  return (
    <div className={`rounded-md border p-3 ${severityClass} border-current/20`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide mb-1 opacity-70">
            {SEVERITY_LABELS[notice.severity]} {title}
          </p>
          <p className="text-sm">{notice.body}</p>
        </div>


          <IconButton
            Icon={Trash2}
            aria-label="Delete notice"
            className="rounded-full text-destructive-foreground bg-destructive"
            onClick={() => noticeDeletion.mutate(notice.id)}
          />
      </div>
      {notice.expires_at && (
        <p className="text-xs opacity-60 mt-1.5">
          Expires {DateTime.fromISO(notice.expires_at).toRelative()}
        </p>
      )}
    </div>
  );
}

interface Props {
  notice: Notice;
}
