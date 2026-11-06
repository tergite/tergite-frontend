import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { DateTime } from "luxon";
import { Copy, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { QasmEditor, type QasmError } from "@/components/ui/qasm-editor";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getUpcomingBookingsQuery } from "@/lib/api/bookings";
import { getDeviceCalibrationQuery } from "@/lib/api/devices";
import type { Device, Project, User } from "@/lib/api/types";
import { useAppStore } from "@/lib/app-state";

const TOKEN_PLACEHOLDER = "MY_API_TOKEN";

/**
 * Where a circuit is written and run: the device, shots, the circuit itself, and what the
 * device, the user's booking and the project's QPU time say about running it now.
 */
export function CircuitPanel({
  devices,
  project,
  currentUser,
  draft,
  onDraftChange,
  onRun,
  isRunning,
  errors,
}: Props) {
  const device = devices.find((v) => v.name === draft.device);
  const apiToken = useAppStore((state) => state.apiToken);
  const { data: calibration } = useQuery({
    ...getDeviceCalibrationQuery(draft.device),
    enabled: !!draft.device,
    throwOnError: false,
  });
  const { data: bookings = [] } = useQuery({
    ...getUpcomingBookingsQuery({
      backend: draft.device,
      user_id: currentUser.id,
      limit: 1,
      shouldThrowOnError: false,
    }),
    enabled: !!draft.device,
    // an offline backend answers with an error, which a retry will not change
    retry: false,
  });
  const frames = useMemo(
    () => calibration?.frames?.map((v) => v.name),
    [calibration],
  );
  const booking = bookings[0];
  const hasQpu = project.qpu_seconds > 0;
  const isRunnable =
    !!device?.is_online && hasQpu && draft.qasm.trim().length > 0;
  const pythonScript = makePythonScript(draft, apiToken);

  return (
    <Card id="circuit" className="flex min-w-0 flex-col">
      <Tabs defaultValue="qasm" className="flex flex-1 flex-col">
        <div className="flex flex-wrap items-end gap-3 border-b p-4">
          <div className="grid min-w-44 flex-1 gap-1.5">
            <Label htmlFor="run-device">Device</Label>
            <Select
              value={draft.device}
              onValueChange={(name) =>
                onDraftChange({ ...draft, device: name })
              }
            >
              <SelectTrigger id="run-device">
                <SelectValue placeholder="Device" />
              </SelectTrigger>
              <SelectContent>
                {devices.map((v) => (
                  <SelectItem
                    key={v.name}
                    value={v.name}
                    disabled={!v.is_online}
                  >
                    {v.name} · {v.number_of_qubits} qubits ·{" "}
                    {v.is_online ? "online" : "offline"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid w-28 gap-1.5">
            <Label htmlFor="run-name">Name</Label>
            <Input
              id="run-name"
              value={draft.name}
              maxLength={64}
              onChange={(event) =>
                onDraftChange({ ...draft, name: event.target.value })
              }
            />
          </div>
          <div className="grid w-24 gap-1.5">
            <Label htmlFor="run-shots">Shots</Label>
            <Input
              id="run-shots"
              type="number"
              min={1}
              value={draft.shots}
              onChange={(event) =>
                onDraftChange({ ...draft, shots: Number(event.target.value) })
              }
            />
          </div>
          <TabsList>
            <TabsTrigger value="qasm">OpenQASM</TabsTrigger>
            <TabsTrigger value="python">Python</TabsTrigger>
          </TabsList>
        </div>

        <dl className="flex flex-wrap gap-x-5 gap-y-1 border-b bg-muted/40 px-4 py-2 text-sm">
          <div className="flex gap-1.5">
            <dt className="text-muted-foreground">Calibrated</dt>
            <dd>{formatWhen(calibration?.last_calibrated)}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="text-muted-foreground">Booking</dt>
            <dd>
              {booking ? (
                formatBooking(booking.start_utc, booking.end_utc)
              ) : (
                <Link to={`/devices/${draft.device}`} className="underline">
                  Book
                </Link>
              )}
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="text-muted-foreground">QPU</dt>
            <dd>
              {hasQpu ? (
                formatSeconds(project.qpu_seconds)
              ) : (
                <Link to="/projects" className="text-destructive underline">
                  None left
                </Link>
              )}
            </dd>
          </div>
        </dl>

        <TabsContent value="qasm" className="mt-0 flex flex-1 flex-col">
          <QasmEditor
            value={draft.qasm}
            onChange={(qasm) => onDraftChange({ ...draft, qasm })}
            onRun={() => isRunnable && !isRunning && onRun()}
            numberOfQubits={device?.number_of_qubits ?? 0}
            frames={frames}
            errors={errors}
            className="h-80 flex-1"
          />
          {errors.length > 0 && (
            <ul
              role="alert"
              className="border-t px-4 py-2 text-sm text-destructive"
            >
              {errors.map((error, index) => (
                <li key={index}>{error.message}</li>
              ))}
            </ul>
          )}
          <div className="flex items-center justify-end gap-3 border-t p-4">
            <kbd className="rounded border px-1.5 py-0.5 text-xs text-muted-foreground">
              ⌘↵
            </kbd>
            <Button onClick={onRun} disabled={!isRunnable || isRunning}>
              <Play className="mr-2 h-4 w-4" />
              {isRunning ? "Running" : "Run"}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="python" className="mt-0 flex-1 p-4">
          <pre className="overflow-x-auto rounded-md bg-muted p-4 font-mono text-[13px] leading-relaxed">
            {pythonScript}
          </pre>
          <div className="mt-3 flex items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {apiToken
                ? "Uses the token from the top bar."
                : "Make a token in the top bar, or under Tokens, for MY_API_TOKEN."}
            </p>
            <Button
              variant="outline"
              onClick={() => navigator.clipboard.writeText(pythonScript)}
            >
              <Copy className="mr-2 h-4 w-4" />
              Copy
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </Card>
  );
}

/** What is about to run */
export interface Draft {
  device: string;
  shots: number;
  name: string;
  qasm: string;
}

interface Props {
  devices: Device[];
  project: Project;
  currentUser: User;
  draft: Draft;
  onDraftChange: (draft: Draft) => void;
  onRun: () => void;
  isRunning: boolean;
  errors: QasmError[];
}

/** The draft as a tergite SDK script, to run it from a notebook instead */
function makePythonScript(draft: Draft, apiToken?: string): string {
  return `from qiskit import qasm3, transpile  # qasm3.loads needs qiskit-qasm3-import
from tergite import Tergite

provider = Tergite.use_provider_account(
    service_name="tergite",
    url="${import.meta.env.VITE_API_BASE_URL}",
    token="${apiToken ?? TOKEN_PLACEHOLDER}",
)
backend = provider.get_backend("${draft.device}")

circuit = qasm3.loads("""
${draft.qasm.trim()}
""")
job = backend.run(transpile(circuit, backend), shots=${draft.shots})
job.wait_for_final_state()
print(job.result().get_counts())
`;
}

function formatWhen(iso?: string | null): string {
  return iso ? (DateTime.fromISO(iso).toRelative() ?? "—") : "—";
}

function formatBooking(startUtc: string, endUtc: string): string {
  const start = DateTime.fromISO(startUtc).toLocal();
  const end = DateTime.fromISO(endUtc).toLocal();
  const day = start.hasSame(DateTime.local(), "day")
    ? ""
    : `${start.toFormat("d LLL")} `;
  return `${day}${start.toFormat("HH:mm")}–${end.toFormat("HH:mm")}`;
}

function formatSeconds(value: number): string {
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`;
}
