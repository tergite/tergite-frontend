import {
  keepPreviousData,
  QueryClient,
  queryOptions,
} from "@tanstack/react-query";
import {
  type AdminCreateProjectBody,
  type AdminProject,
  type Project,
  type UpdateProjectPutBody,
  type User,
} from "./types";
import { client } from "./client";

export const myProjectsQuery = queryOptions({
  queryKey: ["me", "projects"],
  queryFn: async () => {
    const { data } = await client.GET("/me/projects/");
    return data!.data as Project[];
  },
  throwOnError: true,
});

export const myActiveProjectsQuery = queryOptions({
  queryKey: ["me", "projects", "active"],
  queryFn: async () => {
    const { data } = await client.GET("/me/projects/", {
      params: { query: { is_active: true } },
    });
    return data!.data as Project[];
  },
  throwOnError: true,
});

/** All projects, which only admins fetch */
export function getAllAdminProjectsQuery(options: {
  is_active?: boolean;
  currentUser: User;
  skip?: number;
  limit?: number;
}) {
  const { is_active, skip = 0, limit, currentUser } = options;
  return queryOptions({
    queryKey: ["admin", "projects", is_active, limit, skip],
    queryFn: async () => {
      const { data } = await client.GET("/admin/projects/", {
        params: { query: { is_active, limit, skip } },
      });
      return data!.data as AdminProject[];
    },
    enabled: currentUser.roles.includes("admin"),
    throwOnError: true,
  });
}

/** User email addresses, for completing the admin project forms */
export function getUserEmailsQuery(options: { search?: string } = {}) {
  const { search } = options;
  return queryOptions({
    queryKey: ["admin", "user-emails", search],
    queryFn: async () => {
      const { data } = await client.GET("/admin/users/emails/", {
        params: { query: { search: search || undefined } },
      });
      return data!;
    },
    // a directory of addresses does not go stale in the life of a form, and the list
    // must not blank while the next search is in flight
    staleTime: 5 * 60_000,
    refetchInterval: false,
    placeholderData: keepPreviousData,
  });
}

export async function deleteMyProject(id: string): Promise<void> {
  await client.DELETE("/me/projects/{_id}", { params: { path: { _id: id } } });
}

export async function createAdminProject(
  payload: AdminCreateProjectBody,
): Promise<AdminProject> {
  const { data } = await client.POST("/admin/projects/", {
    body: payload,
  });
  return data!;
}

export async function updateAdminProject(
  id: string,
  payload: UpdateProjectPutBody,
): Promise<AdminProject> {
  const { data } = await client.PUT("/admin/projects/{id}", {
    params: { path: { id } },
    body: payload,
  });
  return data!;
}

export async function deleteAdminProject(id: string): Promise<void> {
  await client.DELETE("/admin/projects/{id}", { params: { path: { id } } });
}

export function refreshMyProjectsQueries(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: ["me", "projects"] });
}

export function refreshAllAdminQueries(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: ["admin"] });
}
