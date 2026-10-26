import { queryOptions } from "@tanstack/react-query";
import { type Job } from "./types";
import { client } from "./client";

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
