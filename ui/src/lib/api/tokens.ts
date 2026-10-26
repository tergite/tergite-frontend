import { QueryClient, queryOptions } from "@tanstack/react-query";
import type {
  AppToken,
  AppTokenCreationRequest,
  AppTokenCreationResponse,
  AppTokenUpdateRequest,
} from "./types";
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
