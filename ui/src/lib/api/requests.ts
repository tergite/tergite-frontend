import { QueryClient, queryOptions } from "@tanstack/react-query";
import type {
  Project,
  User,
  UserRequest,
  UserRequestMetadata,
  UserRequestStatus,
  UserRequestType,
} from "./types";
import { client } from "./client";
import { refreshMyNotices } from "./notices";
import { refreshMyProjectsQueries } from "./projects";

/**
 * The requests the current user made, or those awaiting their approval
 *
 * @param options.projectList - the projects the user can see, to name those requested on
 */
export function getMyRequestsQuery(
  options: {
    role?: "requester" | "approver";
    status?: UserRequestStatus;
    types?: UserRequestType[];
    projectList?: Project[];
  } = {},
) {
  const { role = "requester", status, types, projectList = [] } = options;
  const projectIds = projectList.map((v) => v.id).sort();
  return queryOptions({
    queryKey: ["me", "requests", role, status, types, projectIds],
    queryFn: async () => {
      const requests = await getMyRequests({ role, status, types });
      return extendUserRequests(requests, projectList);
    },
    throwOnError: true,
  });
}

/**
 * The requests awaiting an admin, which only admins fetch
 *
 * @param options.projectList - the projects the user can see, to name those requested on
 */
export function getAllUserRequestsQuery(options: {
  status?: UserRequestStatus;
  currentUser: User;
  projectList?: Project[];
  skip?: number;
  limit?: number;
}) {
  const { status, skip = 0, limit, currentUser, projectList = [] } = options;
  const projectIds = projectList.map((v) => v.id).sort();
  return queryOptions({
    queryKey: ["me", "requests", "approver", status, limit, skip, projectIds],
    queryFn: async () => {
      const requests = await getMyRequests({
        role: "approver",
        status,
        limit,
        skip,
      });
      return extendUserRequests(requests, projectList);
    },
    enabled: currentUser.roles.includes("admin"),
    throwOnError: true,
  });
}

/** The current user's requests of the given types on the given projects */
export function getMyProjectsRequestsQuery(options: {
  status?: UserRequestStatus;
  projects: Project[];
  types: UserRequestType[];
}) {
  const { status, projects, types } = options;
  const projectIds = projects.map((v) => v.id).sort();
  return queryOptions({
    queryKey: ["me", "requests", "requester", status, types, projectIds],
    queryFn: async () => {
      const requests = await getMyRequests({ role: "requester", status, types });
      return requests.filter((v) => projectIds.includes(v.resource_id));
    },
    throwOnError: true,
  });
}

export async function requestQpuTimeExtension(
  payload: QpuTimeExtensionPostBody,
): Promise<UserRequest> {
  const { project_id, seconds, reason } = payload;
  const metadata: UserRequestMetadata = { resource: "project", seconds };
  const { data } = await client.POST("/me/requests/", {
    body: {
      type: "project-qpu-seconds",
      resource_id: project_id,
      reason,
      metadata,
    },
  });
  return data! as UserRequest;
}

export async function requestPulseAccess(payload: {
  project_id: string;
  reason: string;
}): Promise<UserRequest> {
  const { data } = await client.POST("/me/requests/", {
    body: {
      type: "project-pulse-access",
      resource_id: payload.project_id,
      reason: payload.reason,
      metadata: { resource: "project" },
    },
  });
  return data! as UserRequest;
}

export async function requestProjectAccess(payload: {
  project_id: string;
  reason: string;
}): Promise<UserRequest> {
  const { data } = await client.POST("/me/requests/", {
    body: {
      type: "project-access",
      resource_id: payload.project_id,
      reason: payload.reason,
    },
  });
  return data! as UserRequest;
}

export async function approveMyRequest(id: string): Promise<UserRequest> {
  const { data } = await client.PUT("/me/requests/{_id}", {
    params: { path: { _id: id } },
    body: { status: "approved" },
  });
  return data! as UserRequest;
}

export async function rejectMyRequest(args: {
  id: string;
  reason?: string;
}): Promise<UserRequest> {
  const { data } = await client.PUT("/me/requests/{_id}", {
    params: { path: { _id: args.id } },
    body: {
      status: "rejected",
      rejection_reason: args.reason,
    },
  });
  return data! as UserRequest;
}

export function refreshMyRequests(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: ["me", "requests"] });
}

/** A decision changes the request, its project and the approvers' notices */
export async function refreshDecisionQueries(queryClient: QueryClient) {
  await refreshMyRequests(queryClient);
  await refreshMyNotices(queryClient);
  await refreshMyProjectsQueries(queryClient);
}

async function getMyRequests(options: {
  role: "requester" | "approver";
  status?: UserRequestStatus;
  types?: UserRequestType[];
  skip?: number;
  limit?: number;
}): Promise<UserRequest[]> {
  const { status, types, ...rest } = options;
  const { data } = await client.GET("/me/requests/", {
    params: { query: { ...rest, status: status && [status], type: types } },
  });
  return data!.data as UserRequest[];
}

function extendUserRequests(
  requests: UserRequest[],
  projectList: Project[],
): ExtendedUserRequest[] {
  const projectMap = Object.fromEntries(projectList.map((v) => [v.id, v]));
  return requests.map((v) => ({
    ...v,
    project_name: projectMap[v.resource_id]?.name,
  }));
}

// a request with the name of its project, where the viewer can see that project
export type ExtendedUserRequest = UserRequest & { project_name?: string };

export type QpuTimeExtensionPostBody = {
  project_id: string;
  seconds: number;
  reason: string;
};
