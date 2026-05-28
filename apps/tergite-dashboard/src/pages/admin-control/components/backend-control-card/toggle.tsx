import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/hooks/use-toast";
import {
  apiBaseUrl,
  devicesQuery,
  singleDeviceQuery,
  switchBackendOn,
  switchBackendOff,
} from "@/lib/api-client";

interface Props {
  deviceName: string;
  isOnline: boolean;
}

export function BackendToggle({ deviceName, isOnline }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const goOnline = useMutation({
    mutationKey: [apiBaseUrl, "admin", "switch", deviceName, "on"],
    async mutationFn() {
      return await switchBackendOn(deviceName);
    },
    async onSuccess() {
      await queryClient.invalidateQueries({ queryKey: devicesQuery.queryKey });
      await queryClient.invalidateQueries({
        queryKey: singleDeviceQuery(deviceName).queryKey,
      });
      toast({ title: "Backend brought online", description: deviceName });
    },
    throwOnError: true,
  });

  const goOffline = useMutation({
    mutationKey: [apiBaseUrl, "admin", "switch", deviceName, "off"],
    async mutationFn() {
      return await switchBackendOff(deviceName);
    },
    async onSuccess() {
      await queryClient.invalidateQueries({ queryKey: devicesQuery.queryKey });
      await queryClient.invalidateQueries({
        queryKey: singleDeviceQuery(deviceName).queryKey,
      });
      toast({ title: "Backend taken offline", description: deviceName });
    },
    throwOnError: true,
  });

  const isLoading = goOnline.isPending || goOffline.isPending;

  return (
    <>
      <div className="rounded-md border p-3 flex items-center justify-between gap-3">
        <div>
          <Label
            htmlFor={`backend-toggle-${deviceName}`}
            className="text-sm font-medium"
          >
            {isOnline ? "Backend enabled" : "Backend disabled"}
          </Label>
          <p className="text-xs text-muted-foreground mt-0.5">
            {isOnline
              ? "Accepting jobs from all users"
              : "Not accepting new jobs"}
          </p>
        </div>

        {isOnline ? (
          <ConfirmDialog
            trigger={
              <Switch
                id={`backend-toggle-${deviceName}`}
                checked={true}
                disabled={isLoading}
                aria-label="Toggle backend online/offline"
              />
            }
            title="Take backend offline?"
            description={`This will stop ${deviceName} from accepting new jobs. Currently queued jobs may be affected. Are you sure?`}
            confirmBtnLabel="Take offline"
            cancelBtnLabel="Cancel"
            onConfirm={() => goOffline.mutate()}
          />
        ) : (
          <Switch
            id={`backend-toggle-${deviceName}`}
            checked={false}
            disabled={isLoading}
            aria-label="Toggle backend online/offline"
            onCheckedChange={() => goOnline.mutate()}
          />
        )}
      </div>

      {!isOnline && (
        <Button
          variant="outline"
          className="w-full border-green-600 text-green-700 hover:bg-green-50 dark:hover:bg-green-950"
          disabled={isLoading}
          onClick={() => goOnline.mutate()}
        >
          Bring backend online
        </Button>
      )}
    </>
  );
}
