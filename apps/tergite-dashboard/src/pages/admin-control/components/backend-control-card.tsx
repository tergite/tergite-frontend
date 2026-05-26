import { useState, useCallback } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { switchBackendOn, switchBackendOff } from "@/lib/api-client";
import { useQueryClient } from "@tanstack/react-query";
import { type Device } from "../../../../types";

interface Props {
  device: Device;
  onStatusChange?: () => void;
}

export function BackendControlCard({ device, onStatusChange }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isLoading, setIsLoading] = useState(false);

  const handleToggleOnline = useCallback(async () => {
    setIsLoading(true);
    try {
      await switchBackendOn(device.name);
      await queryClient.invalidateQueries({ queryKey: ["devices"] });
      onStatusChange?.();
      toast({ title: "Backend brought online", description: device.name });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast({ title: "Failed to set online", description: msg, variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [device.name, queryClient, onStatusChange, toast]);

  const handleToggleOffline = useCallback(async () => {
    setIsLoading(true);
    try {
      await switchBackendOff(device.name);
      await queryClient.invalidateQueries({ queryKey: ["devices"] });
      onStatusChange?.();
      toast({ title: "Backend taken offline", description: device.name });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast({ title: "Failed to set offline", description: msg, variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [device.name, queryClient, onStatusChange, toast]);

  const isOnline = device.is_online;

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardDescription>Backend control</CardDescription>
          <Badge variant={isOnline ? "default" : "destructive"}>
            {isOnline ? "Online" : "Offline"}
          </Badge>
        </div>
        <p className="text-base font-medium">{device.name}</p>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {/* Key metrics */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-md border bg-muted/40 p-3">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Qubits</p>
            <p className="text-xl font-medium tabular-nums">{device.number_of_qubits}</p>
          </div>
          <div className="rounded-md border bg-muted/40 p-3">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Version</p>
            <p className="text-xl font-medium tabular-nums truncate">{device.version}</p>
          </div>
          <div className="rounded-md border bg-muted/40 p-3 col-span-2">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Last online</p>
            <p className="text-sm font-medium tabular-nums text-muted-foreground">
              {device.last_online
                ? new Date(device.last_online).toLocaleString()
                : "—"}
            </p>
          </div>
        </div>

        {/* Qubit health dots */}
        {device.qubit_ids?.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Qubit health</p>
            <div className="flex flex-wrap gap-1">
              {device.qubit_ids.map((qid) => (
                <div
                  key={qid}
                  title={qid}
                  className={`w-4 h-4 rounded-sm ${isOnline ? "bg-green-500" : "bg-muted"}`}
                />
              ))}
            </div>
          </div>
        )}

        {/* Toggle */}
        <div className="rounded-md border p-3 flex items-center justify-between gap-3">
          <div>
            <Label htmlFor={`backend-toggle-${device.name}`} className="text-sm font-medium">
              {isOnline ? "Backend enabled" : "Backend disabled"}
            </Label>
            <p className="text-xs text-muted-foreground mt-0.5">
              {isOnline ? "Accepting jobs from all users" : "Not accepting new jobs"}
            </p>
          </div>

          {isOnline ? (
            <ConfirmDialog
              trigger={
                <Switch
                  id={`backend-toggle-${device.name}`}
                  checked={true}
                  disabled={isLoading}
                  aria-label="Toggle backend online/offline"
                />
              }
              title="Take backend offline?"
              description={`This will stop ${device.name} from accepting new jobs. Currently queued jobs may be affected. Are you sure?`}
              confirmBtnLabel="Take offline"
              cancelBtnLabel="Cancel"
              onConfirm={handleToggleOffline}
            />
          ) : (
            <Switch
              id={`backend-toggle-${device.name}`}
              checked={false}
              disabled={isLoading}
              aria-label="Toggle backend online/offline"
              onCheckedChange={handleToggleOnline}
            />
          )}
        </div>

        {!isOnline && (
          <Button
            variant="outline"
            className="w-full border-green-600 text-green-700 hover:bg-green-50 dark:hover:bg-green-950"
            disabled={isLoading}
            onClick={handleToggleOnline}
          >
            Bring backend online
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
