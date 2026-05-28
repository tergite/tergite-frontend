import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { singleDeviceQuery } from "@/lib/api-client";
import { BackendToggle } from "./toggle";
import { DateTime } from "luxon";

interface Props {
  deviceName: string;
}

export function BackendControlCard({ deviceName }: Props) {
  const { data: device } = useQuery(singleDeviceQuery(deviceName));

  if (!device) return null;

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
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
              Qubits
            </p>
            <p className="text-xl font-medium tabular-nums">
              {device.number_of_qubits}
            </p>
          </div>
          <div className="rounded-md border bg-muted/40 p-3">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
              Version
            </p>
            <p className="text-xl font-medium tabular-nums truncate">
              {device.version}
            </p>
          </div>
          <div className="rounded-md border bg-muted/40 p-3 col-span-2">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
              Last online
            </p>
            <p className="text-sm font-medium tabular-nums text-muted-foreground">
              {device.last_online
                ? DateTime.fromISO(device.last_online).toRelative()
                : "—"}
            </p>
          </div>
        </div>

        <BackendToggle deviceName={deviceName} isOnline={isOnline} />
      </CardContent>
    </Card>
  );
}
