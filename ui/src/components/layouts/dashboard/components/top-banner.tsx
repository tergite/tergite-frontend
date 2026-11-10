import { Copy, RefreshCcw } from "lucide-react";
import { Button, IconButton } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCallback } from "react";
import { useAppStore } from "@/lib/app-state";
import { createAppToken, refreshMyTokensQueries } from "@/lib/api/tokens";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ButtonGroup } from "@/components/ui/button-group";

export function TopBanner({ shouldShowApiToken }: Props) {
  const { apiToken, setApiToken, currentProjectId } = useAppStore();
  const queryClient = useQueryClient();

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

  const handleApiTokenCopy = useCallback(
    () => navigator.clipboard.writeText(apiToken || ""),
    [apiToken]
  );

  return (
    <header
      data-testid="top-banner"
      className="flex justify-end px-4 py-4 sm:px-7"
    >
      <div className="relative flex flex-wrap gap-2 lg:flex-nowrap">
        {shouldShowApiToken && (
          <ButtonGroup className="shadow-sm">
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
  // admin screens have no project selected, so a token minted there would be meaningless
  shouldShowApiToken: boolean;
}
