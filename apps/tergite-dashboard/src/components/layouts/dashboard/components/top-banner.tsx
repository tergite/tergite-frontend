import { Copy, RefreshCcw } from "lucide-react";
import { Button, IconButton } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { AppStateContext } from "@/lib/app-state";
import { createAppToken, refreshMyTokensQueries } from "@/lib/api/tokens";
import { getMyNoticesQuery } from "@/lib/api/notices";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NoticeBanner } from "@/components/ui/notice-banner";
import { DateTime } from "luxon";
import { CUSTOM_NOTICE_TYPES, User } from "../../../../../types";
import { ButtonGroup } from "@/components/ui/button-group";
import { NotificationsBell } from "./notifications";

export function TopBanner({ currentUser, shouldShowApiToken }: Props) {
  const { apiToken, setApiToken, currentProjectId } =
    useContext(AppStateContext);
  const queryClient = useQueryClient();
  const [timestamp, setTimestamp] = useState(DateTime.now().toISO());

  const appTokenCreation = useMutation({
    mutationKey: [
      "me",
      "tokens",
      "?project_id=",
      currentProjectId,
      "post",
    ],
    async mutationFn({ projectId }: { projectId?: string }) {
      if (projectId) {
        return await createAppToken({
          title: `${projectId}-${new Date().getTime()}`,
          project_id: projectId,
          lifespan_seconds: 7_200,
        });
      }
    },
    onSuccess(data) {
      if (data) {
        setApiToken(data.access_token);
        refreshMyTokensQueries(queryClient);
      }
    },
    throwOnError: true,
  });

  const { data: unreadNotices } = useQuery(
    getMyNoticesQuery({ type: CUSTOM_NOTICE_TYPES, is_read: false })
  );
  // the most severe of the announcements in force, earliest first
  const notices = useMemo(
    () =>
      unreadNotices
        ?.filter(
          (v) =>
            (!v.starts_at || v.starts_at <= timestamp) &&
            (!v.expires_at || v.expires_at > timestamp)
        )
        .sort(
          (a, b) =>
            a.severity - b.severity ||
            (a.starts_at ?? "").localeCompare(b.starts_at ?? "")
        ),
    [unreadNotices, timestamp]
  );

  const handleApiTokenCopy = useCallback(
    () => navigator.clipboard.writeText(apiToken || ""),
    [apiToken]
  );

  // FIXME: Use react query, come on!
  useEffect(() => {
    const interval = setInterval(() => {
      setTimestamp(DateTime.now().toISO());
    }, 60000); // Update every minute

    return () => clearInterval(interval);
  }, []);

  return (
    <header data-testid="top-banner" className="flex px-4 sm:px-6 py-4">
      <div className="relative w-full gap-2 flex flex-wrap lg:flex-nowrap">
        <div className="w-full">
          {notices?.slice(0, 1).map((notice) => (
            <NoticeBanner key={notice.id} notice={notice} />
          ))}
          <div className="flex items-center gap-2">
            <NotificationsBell userId={currentUser.id} />
          </div>
        </div>

        {shouldShowApiToken && (
          <ButtonGroup>
            <Button
              variant="outline"
              type="button"
              className="text-sm pr-2 pointer-events-none text-muted-foreground"
            >
              API token
            </Button>
            <Input
              type="password"
              id="api-token"
              value={apiToken || ""}
              readOnly={true}
              className="w-full rounded-l-md rounded-r-none bg-background pr-8  md:w-[320px]"
            />
            <IconButton
              variant="outline"
              className="rounded-none focus:mr-[1px] disabled:text-muted-foreground disabled:bg-muted"
              Icon={RefreshCcw}
              disabled={!currentProjectId || appTokenCreation.isPending}
              onClick={() =>
                appTokenCreation.mutate({ projectId: currentProjectId })
              }
            />
            <IconButton
              variant="outline"
              className="rounded-l-none disabled:text-muted-foreground disabled:bg-muted"
              disabled={!apiToken}
              onClick={handleApiTokenCopy}
              Icon={Copy}
            />
          </ButtonGroup>
        )}
      </div>
    </header>
  );
}

interface Props {
  currentUser: User;
  // admin screens have no project selected, so a token minted there would be meaningless
  shouldShowApiToken: boolean;
}
