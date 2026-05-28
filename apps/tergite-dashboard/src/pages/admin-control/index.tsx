import { useMemo, useState } from "react";
import { useLoaderData } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { QueryClient } from "@tanstack/react-query";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { currentUserQuery, devicesQuery } from "@/lib/api-client";
import { loadOrRedirectIfAuthErr } from "@/lib/utils";
import {
  type AppState,
  type Device,
  type ErrorInfo,
  type User,
  UserRole,
} from "../../../types";
import { BackendControlCard } from "./components/backend-control-card";
import { CalibrationCard } from "./components/calibration-card";
import { NoticesCard } from "./components/notices-card";
import { Activity } from "lucide-react";
import { StatusTile } from "./components/status-tile";

export function AdminControl() {
  const { currentUser } = useLoaderData() as AdminControlData;
  const { data: devices = [] } = useQuery(devicesQuery);

  const [selectedDeviceName, setSelectedDeviceName] = useState<string>(
    () => devices[0]?.name ?? "",
  );

  // Resolve selected device — fall back gracefully
  const selectedDevice = useMemo<Device | undefined>(
    () => devices.find((d) => d.name === selectedDeviceName) ?? devices[0],
    [devices, selectedDeviceName],
  );

  const onlineCount = useMemo(
    () => devices.filter((d) => d.is_online).length,
    [devices],
  );

  return (
    <main className="flex flex-1 flex-col gap-4 p-4 sm:px-6 sm:py-0">
      {/* ── Header ── */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-muted-foreground" />
          <h1 className="text-lg font-medium">Control panel</h1>
          <Badge variant="outline" className="text-xs">
            {onlineCount}/{devices.length} online
          </Badge>
        </div>

        {/* Device selector */}
        {devices.length > 1 && (
          <Select
            value={selectedDevice?.name}
            onValueChange={setSelectedDeviceName}
          >
            <SelectTrigger className="w-48 h-8 text-sm">
              <SelectValue placeholder="Select device" />
            </SelectTrigger>
            <SelectContent>
              {devices.map((d) => (
                <SelectItem key={d.name} value={d.name} className="text-sm">
                  <span className="flex items-center gap-2">
                    <span
                      className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${
                        d.is_online ? "bg-green-500" : "bg-red-400"
                      }`}
                    />
                    {d.name}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* ── System status bar ── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatusTile label="Devices" value={`${devices.length}`} />
        <StatusTile label="Online" value={`${onlineCount}`} />
        <StatusTile
          label="Selected"
          value={selectedDevice?.name ?? "—"}
          statusDot={
            selectedDevice
              ? selectedDevice.is_online
                ? "green"
                : "red"
              : undefined
          }
        />
      </div>

      {/* ── Three-panel grid ── */}
      {selectedDevice ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <BackendControlCard deviceName={selectedDevice.name} />
          <CalibrationCard deviceName={selectedDevice.name} />
          <NoticesCard currentUser={currentUser} />
        </div>
      ) : (
        <div className="flex flex-1 items-center justify-center text-muted-foreground">
          No devices found.
        </div>
      )}
    </main>
  );
}



// eslint-disable-next-line react-refresh/only-export-components
export function loader(_appState: AppState, queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<AdminControlData> => {
    const cachedCurrentUser = queryClient.getQueryData(
      currentUserQuery.queryKey,
    );
    const currentUser =
      cachedCurrentUser ?? (await queryClient.fetchQuery(currentUserQuery));

    if (!currentUser.roles.includes(UserRole.ADMIN)) {
      const error = new Error("user should be an admin") as ErrorInfo;
      error.status = 403;
      throw error;
    }

    // Pre-fetch devices so the page renders immediately
    await queryClient.prefetchQuery(devicesQuery);

    return { currentUser };
  });
}

interface AdminControlData {
  currentUser: User;
}
