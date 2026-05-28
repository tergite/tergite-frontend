import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  const [confirmOpen, setConfirmOpen] = useState(false);

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

  function handleToggle(checked: boolean) {
    if (checked) {
      goOnline.mutate();
    } else {
      setConfirmOpen(true);
    }
  }

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

        <Switch
          id={`backend-toggle-${deviceName}`}
          checked={isOnline}
          disabled={isLoading}
          aria-label="Toggle backend online/offline"
          onCheckedChange={handleToggle}
        />
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Take backend offline?</DialogTitle>
            <DialogDescription className="py-5">
              This will stop {deviceName} from accepting new jobs. Currently
              queued jobs may be affected. Are you sure?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <div className="grid grid-cols-2 gap-2 w-full">
              <Button
                type="button"
                variant="default"
                onClick={() => {
                  setConfirmOpen(false);
                  goOffline.mutate();
                }}
              >
                Take offline
              </Button>
              <Button
                type="button"
                variant="outline"
                className="text-destructive border-destructive"
                onClick={() => setConfirmOpen(false)}
              >
                Cancel
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
