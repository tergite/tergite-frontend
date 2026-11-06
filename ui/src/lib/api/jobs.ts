import { QueryClient, queryOptions } from "@tanstack/react-query";
import type { Job, JobStatus, JobSubmission } from "./types";
import { client } from "./client";

// a running job is polled this often, until it is final
const RUNNING_JOB_REFETCH_MS = 2_000;
const FINAL_STATUSES: JobStatus[] = ["successful", "failed", "cancelled"];

export function getMyJobsQuery(options: { project_id?: string } = {}) {
  const { project_id } = options;
  return queryOptions({
    queryKey: ["me", "jobs", project_id ?? ""],
    queryFn: async () => {
      const { data } = await client.GET("/me/jobs/", {
        params: { query: { project_id } },
      });
      return data!.data as Job[];
    },
    throwOnError: true,
  });
}

/** One of the user's jobs, polled every 2 s until it is final */
export function getMyJobQuery(jobId: string) {
  return queryOptions({
    queryKey: ["me", "jobs", "one", jobId],
    queryFn: async () => {
      const { data } = await client.GET("/me/jobs/{job_id}", {
        params: { path: { job_id: jobId } },
      });
      return data! as Job;
    },
    refetchInterval: (query) =>
      isFinal(query.state.data?.status) ? false : RUNNING_JOB_REFETCH_MS,
  });
}

/** Runs OpenQASM 3 circuits on a device; a circuit it cannot run fails with a 422 */
export async function submitMyJob(body: JobSubmission): Promise<Job> {
  const { data } = await client.POST("/me/jobs/", { body });
  return data! as Job;
}

export async function cancelMyJob(jobId: string): Promise<void> {
  await client.POST("/jobs/{job_id}/cancel", {
    params: { path: { job_id: jobId } },
    body: { reason: "cancelled from the dashboard" },
  });
}

/** Where the browser downloads a job's logfile, which MSS fetches from the backend */
export function getMyJobLogfileUrl(jobId: string): string {
  return `${import.meta.env.VITE_API_BASE_URL}/me/jobs/${jobId}/logfile`;
}

export function isFinal(status?: JobStatus | null): boolean {
  return !!status && FINAL_STATUSES.includes(status);
}

export function refreshMyJobsQueries(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: ["me", "jobs"] });
}
