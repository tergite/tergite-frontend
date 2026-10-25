import { QueryClient, queryOptions } from "@tanstack/react-query";
import {
  type ExtendedUserRequest,
  type Project,
  type QpuTimeExtensionPostBody,
  type User,
  type UserRequest,
  type UserRequestMetadata,
  UserRequestStatus,
  UserRequestType,
  UserRole,
} from "../../../types";
import { client } from "./client";

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
    enabled: currentUser.roles.includes(UserRole.ADMIN),
    throwOnError: true,
  });
}

/** The current user's QPU-time requests on the given projects */
export function getMyProjectsQpuTimeRequestsQuery(options: {
  status?: UserRequestStatus;
  projects: Project[];
}) {
  const { status, projects } = options;
  const projectIds = projects.map((v) => v.id).sort();
  const types = [UserRequestType.PROJECT_QPU_SECONDS];
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
  const metadata = { resource: "project", seconds } as UserRequestMetadata;
  const { data } = await client.POST("/me/requests/", {
    body: {
      type: UserRequestType.PROJECT_QPU_SECONDS,
      resource_id: project_id,
      reason,
      metadata,
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
      type: UserRequestType.PROJECT_ACCESS,
      resource_id: payload.project_id,
      reason: payload.reason,
    },
  });
  return data! as UserRequest;
}

export async function approveMyRequest(id: string): Promise<UserRequest> {
  const { data } = await client.PUT("/me/requests/{_id}", {
    params: { path: { _id: id } },
    body: { status: UserRequestStatus.APPROVED },
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
      status: UserRequestStatus.REJECTED,
      rejection_reason: args.reason,
    },
  });
  return data! as UserRequest;
}

export function refreshMyRequests(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: ["me", "requests"] });
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
