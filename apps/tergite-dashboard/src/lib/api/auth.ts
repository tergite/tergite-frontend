import { QueryClient, queryOptions } from "@tanstack/react-query";
import { type AuthProviderResponse } from "./types";
import type { AppState } from "../app-state";
import { client } from "./client";

export const currentUserQuery = queryOptions({
  queryKey: ["me"],
  queryFn: async () => {
    const { data } = await client.GET("/me/profile");
    return data!;
  },
  refetchInterval: false,
  throwOnError: true,
});

/** The auth providers that users with this email address may log in with */
export async function getAuthProviders(
  email: string,
): Promise<AuthProviderResponse[]> {
  const email_domain = email.split("@")[1];
  const { data } = await client.GET("/auth/providers/", {
    params: { query: { email_domain } },
  });
  return data!.data;
}

export async function logout(queryClient: QueryClient, appState: AppState) {
  appState.clear();
  queryClient.clear();
  await client.POST("/auth/logout");
}
