import { useState } from "react";
import { Link, useLoaderData, useSearchParams } from "react-router-dom";
import {
  QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type { QasmError } from "@/components/ui/qasm-editor";
import { currentUserQuery } from "@/lib/api/auth";
import type { ErrorInfo } from "@/lib/api/client";
import { devicesQuery } from "@/lib/api/devices";
import {
  cancelMyJob,
  getMyJobQuery,
  getMyJobsQuery,
  refreshMyJobsQueries,
  submitMyJob,
} from "@/lib/api/jobs";
import { myActiveProjectsQuery } from "@/lib/api/projects";
import type { Device, Job, Project, User } from "@/lib/api/types";
import { useAppStore } from "@/lib/app-state";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { BELL_CIRCUIT } from "@/lib/qasm/language";
import { CircuitPanel, type Draft } from "./components/circuit-panel";
import { ResultsPanel } from "./components/results-panel";
import { RunsList } from "./components/runs-list";

const DEFAULT_SHOTS = 1024;
const DEFAULT_NAME = "circuit";

/**
 * Runs OpenQASM 3 on a device and shows how it went: write, run, read the results, and come
 * back to past runs to load, resubmit or cancel them.
 */
export function Run() {
  const {
    devices: defaultDevices,
    projects,
    currentUser,
    jobs: defaultJobs,
    openedJob,
  } = useLoaderData() as RunData;
  const queryClient = useQueryClient();
  const currentProjectId = useAppStore((state) => state.currentProjectId);
  const project = projects.find((v) => v.id === currentProjectId);
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedJobId = searchParams.get("job") ?? undefined;

  const { data: devices = defaultDevices } = useQuery(devicesQuery);
  const { data: jobs = defaultJobs } = useQuery(
    getMyJobsQuery({ project_id: project?.id }),
  );
  const { data: selectedJob } = useQuery({
    ...getMyJobQuery(selectedJobId ?? ""),
    enabled: !!selectedJobId,
  });
  const [draft, setDraft] = useState<Draft>(
    () =>
      (openedJob && getDraftFromJob(openedJob)) ?? {
        device: pickDefaultDevice(devices),
        shots: DEFAULT_SHOTS,
        name: DEFAULT_NAME,
        qasm: BELL_CIRCUIT,
      },
  );

  const submission = useMutation({
    mutationFn: submitMyJob,
    onSuccess: async (job) => {
      setSearchParams({ job: job.job_id });
      await refreshMyJobsQueries(queryClient);
    },
  });
  const cancellation = useMutation({
    mutationFn: cancelMyJob,
    onSuccess: () => refreshMyJobsQueries(queryClient),
  });

  const runDraft = (from: Draft) =>
    project &&
    submission.mutate({
      project_id: project.id,
      device: from.device,
      shots: from.shots,
      meas_level: 2,
      meas_return: "single",
      circuits: [{ name: from.name || DEFAULT_NAME, qasm: from.qasm }],
    });
  const openJob = (job: Job) => {
    setSearchParams({ job: job.job_id });
    const loaded = getDraftFromJob(job);
    if (loaded) {
      setDraft(loaded);
      submission.reset();
    }
  };
  const submitJobAgain = (job: Job) => {
    const loaded = getDraftFromJob(job);
    if (loaded) {
      setDraft(loaded);
      runDraft(loaded);
    }
  };
  const updateDraft = (next: Draft) => {
    setDraft(next);
    if (submission.isError) {
      submission.reset();
    }
  };

  return (
    <main className="grid flex-1 content-start items-start gap-4 p-4 sm:px-6 sm:py-0">
      {project ? (
        <>
          <div className="grid gap-4 xl:grid-cols-2">
            <CircuitPanel
              devices={devices}
              project={project}
              currentUser={currentUser}
              draft={draft}
              onDraftChange={updateDraft}
              onRun={() => runDraft(draft)}
              isRunning={submission.isPending}
              errors={getQasmErrors(submission.error)}
            />
            <ResultsPanel
              job={selectedJob}
              onCancel={(jobId) => cancellation.mutate(jobId)}
              isCancelling={cancellation.isPending}
            />
          </div>
          <RunsList
            jobs={jobs}
            selectedJobId={selectedJobId}
            onOpen={openJob}
            onResubmit={submitJobAgain}
            onCancel={(job) => cancellation.mutate(job.job_id)}
          />
        </>
      ) : (
        <p
          id="run-no-project"
          className="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground"
        >
          Pick a project in the top bar to run circuits; its QPU time pays for
          them.{" "}
          <Link to="/projects" className="underline">
            Projects
          </Link>
        </p>
      )}
    </main>
  );
}

interface RunData {
  devices: Device[];
  projects: Project[];
  currentUser: User;
  jobs: Job[];
  // the run the URL opens, whose circuit the editor starts with
  openedJob?: Job;
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async ({ request }): Promise<RunData> => {
    const [devices, projects, currentUser] = await Promise.all([
      queryClient.ensureQueryData(devicesQuery),
      queryClient.ensureQueryData(myActiveProjectsQuery),
      queryClient.ensureQueryData(currentUserQuery),
    ]);
    const jobId = new URL(request.url).searchParams.get("job");
    const openedJob = jobId
      ? await queryClient.ensureQueryData(getMyJobQuery(jobId))
      : undefined;
    if (openedJob && !useAppStore.getState().currentProjectId) {
      // a run opened by its link shows in its own project
      useAppStore
        .getState()
        .setCurrentProjectId(openedJob.project_id ?? undefined);
    }
    const { currentProjectId } = useAppStore.getState();
    const project = projects.find((v) => v.id === currentProjectId);
    const jobs = await queryClient.ensureQueryData(
      getMyJobsQuery({ project_id: project?.id }),
    );
    return { devices, projects, currentUser, jobs, openedJob };
  });
}

/** The first online device, else the first */
function pickDefaultDevice(devices: Device[]): string {
  return (devices.find((v) => v.is_online) ?? devices[0])?.name ?? "";
}

/** The draft a past job ran, if it was submitted from the dashboard */
function getDraftFromJob(job: Job): Draft | undefined {
  const circuit = job.source?.circuits[0];
  if (!job.source || !circuit) {
    return undefined;
  }
  return {
    device: job.device,
    shots: job.source.shots,
    name: circuit.name,
    qasm: circuit.qasm,
  };
}

/** The errors MSS found in the circuit, at their line and column, from its 422 */
function getQasmErrors(error: Error | null): QasmError[] {
  const info = error as ErrorInfo | null;
  if (!info) {
    return [];
  }
  if (info.status !== 422 || !Array.isArray(info.detail)) {
    return [{ message: info.message }];
  }
  return info.detail.map((item) => ({
    message: item.msg,
    line: item.ctx?.line,
    column: item.ctx?.column,
  }));
}
