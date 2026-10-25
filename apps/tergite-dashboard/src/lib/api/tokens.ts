import { QueryClient, queryOptions } from "@tanstack/react-query";
import type {
  AppToken,
  AppTokenCreationRequest,
  AppTokenCreationResponse,
  AppTokenUpdateRequest,
  ExtendedAppToken,
  Project,
} from "../../../types";
import { DateTime } from "luxon";
import { client } from "./client";

export function getMyTokensQuery(options: { project_id?: string } = {}) {
  const { project_id } = options;
  return queryOptions({
    queryKey: ["me", "tokens", project_id],
    queryFn: async () => {
      const { data } = await client.GET("/me/tokens/", {
        params: { query: { project_id: project_id ? [project_id] : undefined } },
      });
      return data!.data as AppToken[];
    },
    throwOnError: true,
  });
}

/** Names each token's project, leaving out the tokens of projects not in the list */
export function addProjectNames(
  tokens: AppToken[],
  projects: Project[],
): ExtendedAppToken[] {
  const projectMap = Object.fromEntries(projects.map((v) => [v.id, v]));
  return tokens
    .filter((v) => projectMap[v.project_id])
    .map((v) => extendAppToken(v, projectMap[v.project_id]));
}

export async function createAppToken(
  payload: AppTokenCreationRequest,
): Promise<AppTokenCreationResponse> {
  const { data } = await client.POST("/me/tokens/", { body: payload });
  return data!;
}

export async function updateAppToken(
  id: string,
  payload: AppTokenUpdateRequest,
): Promise<AppToken> {
  const { data } = await client.PUT("/me/tokens/{_id}", {
    params: { path: { _id: id } },
    body: payload,
  });
  return data!;
}

export async function deleteMyToken(id: string): Promise<void> {
  await client.DELETE("/me/tokens/{_id}", { params: { path: { _id: id } } });
}

export function refreshMyTokensQueries(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: ["me", "tokens"] });
}

export function extendAppToken(
  token: AppToken,
  project: Project,
): ExtendedAppToken {
  const expires_at = DateTime.fromISO(token.created_at).plus({
    seconds: token.lifespan_seconds,
  });
  const is_expired = DateTime.now() > expires_at;
  return { ...token, expires_at, is_expired, project_name: project.name };
}
