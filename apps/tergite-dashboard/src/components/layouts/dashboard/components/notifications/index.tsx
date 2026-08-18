import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  markAllNotificationsRead,
  myNotificationsQuery,
  notificationCountQuery,
  refreshMyNotifications,
} from "@/lib/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellIcon } from "lucide-react";
import { NotificationItem } from "./notification-item";

export function NotificationsBell() {
  const queryClient = useQueryClient();
  const { data: notifications = [] } = useQuery(
    myNotificationsQuery({ limit: 20 }),
  );
  const { data: unreadCount = 0 } = useQuery(
    notificationCountQuery({ is_read: false }),
  );

  const markAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: async () => await refreshMyNotifications(queryClient),
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
          <BellIcon className="h-4 w-4" />
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
              onClick={() => markAll.mutate({})}
              disabled={markAll.isPending}
            >
              Mark all read
            </Button>
          )}
        </div>

        {notifications.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground text-center">
            Nothing to show yet
          </p>
        ) : (
          <ul>
            {notifications.map((notification) => (
              <NotificationItem
                key={notification.id}
                notification={notification}
              />
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
