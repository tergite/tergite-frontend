import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  dismissAllMyNotices,
  getMyNoticesQuery,
  getNoticeCountQuery,
  refreshMyNotices,
} from "@/lib/api/notices";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellIcon } from "lucide-react";
import { NotificationItem } from "./notification-item";

export function NotificationsBell({ userId }: Props) {
  const queryClient = useQueryClient();
  const { data: notices = [] } = useQuery(
    getMyNoticesQuery({ limit: 20, is_read: false })
  );
  // user_id, or a superuser would count everyone's notices
  const { data: unreadCount = 0 } = useQuery(
    getNoticeCountQuery({ user_id: userId, is_read: false }),
  );

  const markAll = useMutation({
    mutationFn: dismissAllMyNotices,
    onSuccess: async () => await refreshMyNotices(queryClient),
    throwOnError: true,
  });

  return (
    <Popover>
      <PopoverTrigger asChild>
        {/* a plain Button rather than IconButton, which renders no children */}
        <Button
          data-cy-notifications-bell
          aria-label="Notifications"
          variant="outline"
          size="icon"
          className="relative"
        >
          <BellIcon className="h-4 w-4" data-testid="notices-bell-icon" />
          {unreadCount > 0 && (
            <Badge
              data-cy-unread-count
              variant="default"
              className="absolute -top-2 -right-2 px-1.5 py-0 text-xs"
            >
              {unreadCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        id="notifications-panel"
        align="end"
        className="w-96 p-0 max-h-96 overflow-y-auto"
      >
        <div className="flex items-center justify-between px-4 py-2 border-b">
          <span className="font-semibold text-sm">Notifications</span>
          {unreadCount > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              data-cy-mark-all-read
              className="text-xs"
              onClick={() => markAll.mutate()}
              disabled={markAll.isPending}
            >
              Mark all read
            </Button>
          )}
        </div>

        {notices.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground text-center">
            Nothing to show yet
          </p>
        ) : (
          <ul>
            {notices.map((notice) => (
              <NotificationItem key={notice.id} notice={notice} />
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}

interface Props {
  userId: string;
}
