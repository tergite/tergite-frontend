import { IconButton } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import {
  apiBaseUrl,
  dismissNotice,
  refreshAllNoticeCounts,
  refreshAllNotices,
} from "@/lib/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useMemo } from "react";
import { NoticeSeverity, Notice } from "../../../types";
import { SEVERITY_LABELS } from "@/lib/utils";

const SEVERITY_BADGE_CLASSES: Record<NoticeSeverity, string> = {
  [NoticeSeverity.INFO]:
    "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  [NoticeSeverity.WARNING]:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  [NoticeSeverity.CRITICAL]:
    "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

export function NoticeBanner({ notice }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const severityClass = SEVERITY_BADGE_CLASSES[notice.severity];
  const title = useMemo(
    () => (notice.target_user_ids ? "" : " · All users"),
    [notice.target_user_ids],
  );

  const noticeDismissal = useMutation({
    mutationKey: [apiBaseUrl, "admin", "notices", "dismiss", notice.id],
    async mutationFn(id: string) {
      return await dismissNotice(id, { baseUrl: apiBaseUrl });
    },
    async onSuccess(data) {
      await refreshAllNotices(queryClient);
      await refreshAllNoticeCounts(queryClient);
      toast({ title: `Notice dismissal: ${data.status}` });
    },
    throwOnError: true,
  });

  return (
    <div className={`rounded-md border p-3 ${severityClass} border-current/20`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex justify-between gap-2">
            <div className="text-xs font-medium uppercase tracking-wide mb-1 opacity-70">
              {SEVERITY_LABELS[notice.severity]} {title}
            </div>
            <IconButton
              Icon={X}
              size="xs"
              variant="ghost"
              aria-label="Dismiss notice"
              className="rounded-full text-xs"
              onClick={() => noticeDismissal.mutate(notice.id)}
            />
          </div>
          <p className="text-sm">{notice.message}</p>
        </div>
      </div>
    </div>
  );
}

interface Props {
  notice: Notice;
}
