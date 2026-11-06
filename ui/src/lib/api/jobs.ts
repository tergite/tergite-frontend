import { QueryClient, queryOptions } from "@tanstack/react-query";
import type { Job, JobStatus, JobSubmission } from "./types";
import { client } from "./client";

// a job not yet final is polled often while it is young, and less as it waits in the queue:
// [up to this age in ms, poll every ms], the last for any older job
const POLL_INTERVALS: [number, number][] = [
  [60_000, 2_000],
  [600_000, 10_000],
  [Infinity, 30_000],
];
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

/**
 * One of the user's jobs, polled until it is final: every 2 s in its first minute, every
 * 10 s up to ten minutes, then every 30 s, as a job waiting out a booking can wait for hours
 */
export function getMyJobQuery(jobId: string) {
  return queryOptions({
    queryKey: ["me", "jobs", "one", jobId],
    queryFn: async () => {
      const { data } = await client.GET("/me/jobs/{job_id}", {
        params: { path: { job_id: jobId } },
      });
      return data! as Job;
    },
    refetchInterval: (query) => {
      const job = query.state.data;
      return isFinal(job?.status) ? false : getPollInterval(job?.created_at);
    },
  });
}

/** How often to poll a job not yet final, from how long ago it was created */
export function getPollInterval(createdAt?: string, now = Date.now()): number {
  const age = createdAt ? now - Date.parse(createdAt) : 0;
  return POLL_INTERVALS.find(([maxAge]) => age < maxAge)![1];
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
