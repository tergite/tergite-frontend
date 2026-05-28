import { BellIcon, Copy, RefreshCcw } from "lucide-react";
import { Button, IconButton } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCallback, useContext, useEffect, useState } from "react";
import { AppStateContext } from "@/lib/app-state";
import { copyToClipboard } from "@/lib/utils";
import {
  createAppToken,
  refreshMyTokensQueries,
  apiBaseUrl,
  noticesQuery,
  noticeCountQuery,
} from "@/lib/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NoticeBanner } from "@/components/ui/notice-banner";
import { DateTime } from "luxon";
import { User } from "types";
import { ButtonGroup } from "@/components/ui/button-group";
import { Badge } from "@/components/ui/badge";

export function TopBanner({ currentUser }: Props) {
  const { apiToken, setApiToken, currentProjectExtId } =
    useContext(AppStateContext);
  const queryClient = useQueryClient();
  const [timestamp, setTimestamp] = useState(DateTime.now().toISO());
  const filters = {
    user_id: currentUser?.id,
    max_start_utc: timestamp,
    min_expires_utc: timestamp,
    include_dismissed: false,
  };

  const appTokenCreation = useMutation({
    mutationKey: [
      apiBaseUrl,
      "me",
      "tokens",
      "?project_ext_id=",
      currentProjectExtId,
      "post",
    ],
    async mutationFn({ projectExtId }: { projectExtId?: string }) {
      if (projectExtId) {
        return await createAppToken({
          title: `${projectExtId}-${new Date().getTime()}`,
          project_ext_id: projectExtId,
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

  const { data: notices } = useQuery(
    noticesQuery({
      ...filters,
      sort: ["severity_number", "starts_at"],
    }),
  );
  const { data: noticeCount } = useQuery(noticeCountQuery(filters));

  const handleApiTokenCopy = useCallback(
    () => copyToClipboard(apiToken || ""),
    [apiToken],
  );

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
          <Badge variant="outline">
            {noticeCount}
            <BellIcon data-icon="inline-end" size={12} />
          </Badge>
        </div>

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
            disabled={!currentProjectExtId || appTokenCreation.isPending}
            onClick={() =>
              appTokenCreation.mutate({ projectExtId: currentProjectExtId })
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
      </div>
    </header>
  );
}

interface Props {
  currentUser: User;
}
