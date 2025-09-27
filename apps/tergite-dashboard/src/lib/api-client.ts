import { QueryClient, queryOptions } from "@tanstack/react-query";
import {
  type AppState,
  type Device,
  type DeviceCalibration,
  type ErrorInfo,
  type Job,
  type AuthProviderResponse,
  type Project,
  type AppTokenCreationRequest,
  type AppTokenCreationResponse,
  type PaginatedData,
  type AppToken,
  type AppTokenUpdateRequest,
  QpuTimeExtensionPostBody,
  QpuTimeExtensionUserRequest,
  User,
  UserRequestStatus,
  UserRequest,
  UserRole,
  AdminProject,
  UpdateProjectPutBody,
  AdminCreateProjectBody,
  Booking,
} from "../../types";
import { normalizeCalibrationData, extendAppToken } from "./utils";

export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
export const refetchInterval = parseFloat(
  import.meta.env.VITE_REFETCH_INTERVAL_MS || "120000"
); // default: 2 minutes

/**
 * the devices query for using with react query
 */
export const devicesQuery = queryOptions({
  queryKey: [apiBaseUrl, "devices"],
  queryFn: async () => await getDevices(),
  refetchInterval,
  throwOnError: true,
});

/**
 * the single device query for using with react query
 * @param options - extra options for filtering
 *          - baseUrl - the base URL of the API
 */
export function singleDeviceQuery(
  name: string,
  options: { baseUrl?: string } = {}
) {
  const { baseUrl = apiBaseUrl } = options;
  return queryOptions({
    queryKey: [baseUrl, "devices", name],
    queryFn: async () => await getDeviceDetail(name),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * the devices query for using with react query
 */
export const calibrationsQuery = queryOptions({
  queryKey: [apiBaseUrl, "calibrations"],
  queryFn: async () => await getCalibrations(),
  refetchInterval,
  throwOnError: true,
});

/**
 * the devices query for using with react query
 */
export const currentUserQuery = queryOptions({
  queryKey: [apiBaseUrl, "me"],
  queryFn: async () => await getCurrentUser(),
  throwOnError: true,
});

/**
 * the single device's calibration query for using with react query
 * @param options - extra options for filtering
 *          - baseUrl - the base URL of the API
 */
export function singleDeviceCalibrationQuery(
  name: string,
  options: { baseUrl?: string } = {}
) {
  const { baseUrl = apiBaseUrl } = options;
  return queryOptions({
    queryKey: [baseUrl, "calibrations", name],
    queryFn: async () => await getCalibrationsForDevice(name),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * the my jobs query for using with react query
 * @param options - extra options for filtering the jobs
 *          - baseUrl - the base URL of the API
 */
export function myJobsQuery(
  options: { project_id?: string; baseUrl?: string } = {}
) {
  const { project_id = "", baseUrl = apiBaseUrl } = options;
  return queryOptions({
    queryKey: [baseUrl, "me", "jobs", project_id],
    queryFn: async () => await getMyJobs(options),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * the my tokens query for using with react query
 * @param options - extra options for filtering the tokens
 *            - baseUrl - the base URL of the API
 *            - project_ext_id - the external ID of the tokens' project
 *            - projectList - List of all available projects
 */
export function myTokensQuery(options: {
  project_ext_id?: string;
  projectList: Project[];
  baseUrl?: string;
}) {
  const { project_ext_id, projectList, baseUrl = apiBaseUrl } = options;
  const queryKey = [baseUrl, "me", "tokens", project_ext_id];

  return queryOptions({
    queryKey,
    queryFn: async () => {
      const rawTokens = await getMyTokens({ project_ext_id });
      const projectMap: { [k: string]: Project } = Object.fromEntries(
        projectList.map((v) => [v.ext_id, { ...v }])
      );

      return rawTokens
        .map(
          (v) =>
            projectMap[v.project_ext_id] &&
            extendAppToken(v, projectMap[v.project_ext_id])
        )
        .filter((v) => !!v);
    },
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * the my projects query for using with react query
 */
export const myProjectsQuery = queryOptions({
  queryKey: [apiBaseUrl, "me", "projects"],
  queryFn: async () => await getMyProjects(),
  refetchInterval,
  throwOnError: true,
});

/**
 * the react query for the active projects for the current user
 */
export const myActiveProjectsQuery = queryOptions({
  queryKey: [apiBaseUrl, "me", "projects", "active"],
  queryFn: async () => await getMyProjects(apiBaseUrl, { is_active: "true" }),
  refetchInterval,
  throwOnError: true,
});

/**
 * the react query for getting all user requests
 * @param options - extra options for filtering the requests
 *            - currentUser - the current user
 *            - baseUrl - the base URL of the API
 *            - status - the status of the requests
 *            - skip - the number of records to skip
 *            - limit - the maximum number of records to return
 */
export function allUserRequestsQuery(options: {
  status?: UserRequestStatus;
  currentUser: User;
  baseUrl?: string;
  skip?: number;
  limit?: number;
}) {
  const {
    status,
    baseUrl = apiBaseUrl,
    skip = 0,
    limit,
    currentUser,
  } = options;
  const queryKey = [baseUrl, "admin", "user-requests", status, limit, skip];
  // run only for admins
  const enabled = currentUser.roles.includes(UserRole.ADMIN);

  return queryOptions({
    queryKey,
    queryFn: async () =>
      await getUserRequests(baseUrl, { status, limit, skip }),
    refetchInterval,
    enabled,
    throwOnError: true,
  });
}

/**
 * the react query for getting all admin projects
 * @param options - extra options for filtering the projects
 *            - baseUrl - the base URL of the API
 *            - is_active - whether the project is active or not
 *            - skip - the number of records to skip
 *            - limit - the maximum number of records to return
 */
export function allAdminProjectsQuery(options: {
  is_active?: boolean;
  currentUser: User;
  baseUrl?: string;
  skip?: number;
  limit?: number;
}) {
  const {
    is_active,
    baseUrl = apiBaseUrl,
    skip = 0,
    limit,
    currentUser,
  } = options;
  const queryKey = [baseUrl, "admin", "user-requests", status, limit, skip];
  // run only for admins
  const enabled = currentUser.roles.includes(UserRole.ADMIN);

  return queryOptions({
    queryKey,
    queryFn: async () =>
      await getAdminProjects(baseUrl, { is_active, limit, skip }),
    refetchInterval,
    enabled,
    throwOnError: true,
  });
}

/**
 * the query for getting the qpu time requests for my projects using with react query
 * @param options - extra options for filtering the tokens
 *            - baseUrl - the base URL of the API
 *            - projectList - List of all available projects
 *            - status - the status of the queries
 */
export function myProjectsQpuTimeRequestsQuery(options: {
  status?: UserRequestStatus;
  projects: Project[];
  baseUrl?: string;
}) {
  const { status, projects, baseUrl = apiBaseUrl } = options;
  const projectIds = projects.map((v) => v.id).sort();
  const queryKey = [baseUrl, "admin", "qpu-time-requests", projectIds, status];

  return queryOptions({
    queryKey,
    queryFn: async () =>
      await getProjectQpuTimeRequests(baseUrl, projectIds, status),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * the react query for getting bookings of given backend
 * @param options - extra options for filtering the requests
 *            - baseUrl - the base URL of the API
 *            - user_id - the ID of the user whose bookings ar eto be got
 *            - min_start_utc - the minimum start UTC datetime for getting a range of bookings
 *            - max_start_utc - the maximum start UTC datetime for getting a range of bookings
 *            - skip - the number of records to skip
 *            - limit - the maximum number of records to return
 */
export function bookingsOfBackendQuery(options: {
  backend: string;
  baseUrl?: string;
  user_id?: string;
  min_start_utc?: string;
  max_start_utc?: string;
  skip?: string;
  limit?: string;
}) {
  const {
    baseUrl = apiBaseUrl,
    skip = "0",
    backend,
    limit,
    user_id,
    min_start_utc,
    max_start_utc,
  } = options;
  const queryKey = [
    baseUrl,
    "bookings",
    backend,
    user_id,
    min_start_utc,
    max_start_utc,
    limit,
    skip,
  ];

  return queryOptions({
    queryKey,
    queryFn: async () =>
      await getBookingsOfBackend(baseUrl, backend, {
        user_id,
        min_start_utc,
        max_start_utc,
        limit,
        skip,
      }),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * Refreshes the queries for the tokens from the API
 *
 * @param queryClient - the query client for making queries
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function refreshMyTokensQueries(
  queryClient: QueryClient,
  options: {
    baseUrl?: string;
  } = {}
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({ queryKey: [baseUrl, "me", "tokens"] });
}

/**
 * Refreshes the queries for the projects from the API
 *
 * @param queryClient - the query client for making queries
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function refreshMyProjectsQueries(
  queryClient: QueryClient,
  options: {
    baseUrl?: string;
  } = {}
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({
    queryKey: [baseUrl, "me", "projects"],
  });
}

/**
 * Refreshes the queries for the QPU time requests from the API
 *
 * @param queryClient - the query client for making queries
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function refreshMyProjectsQpuTimeRequestsQueries(
  queryClient: QueryClient,
  options: {
    baseUrl?: string;
  } = {}
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({
    queryKey: [baseUrl, "admin", "qpu-time-requests"],
  });
}

/**
 * Refreshes the queries for the user requests from the API
 *
 * @param queryClient - the query client for making queries
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function refreshAllRequestsQueries(
  queryClient: QueryClient,
  options: {
    baseUrl?: string;
  } = {}
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({
    queryKey: [baseUrl, "admin", "user-requests"],
  });
}

/**
 * Refreshes the queries for any admin things
 *
 * @param queryClient - the query client for making queries
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function refreshAllAdminQueries(
  queryClient: QueryClient,
  options: {
    baseUrl?: string;
  } = {}
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({ queryKey: [baseUrl, "admin"] });
}

/**
 * Generates a new app token
 * @param payload - the payload for a new app token
 * @param options - the options for loging in including:
 *          - baseUrl - the base URL of the API
 */
export async function createAppToken(
  payload: AppTokenCreationRequest,
  options: {
    baseUrl?: string;
  } = {}
): Promise<AppTokenCreationResponse> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/me/tokens/`, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Updates the app token
 * @param id - the id for the token
 * @param payload - the payload for the update
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function updateAppToken(
  id: string,
  payload: AppTokenUpdateRequest,
  options: {
    baseUrl?: string;
  } = {}
): Promise<AppToken> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/me/tokens/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Requests for more QPU time for the given project
 *
 * @param payload - the body to be sent in the request
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function requestQpuTimeExtension(
  payload: QpuTimeExtensionPostBody,
  options: {
    baseUrl?: string;
  } = {}
): Promise<QpuTimeExtensionUserRequest> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/admin/qpu-time-requests/`, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Gets the auth providers that the given email address might find possible to login with
 * @param email - the email of the user
 * @param options - the options for loging in including:
 *          - baseUrl - the base URL of the API
 * @returns - the auth provider for the given email or raises a 404 error
 */
export async function getAuthProviders(
  email: string,
  options: {
    baseUrl?: string;
  } = {}
): Promise<AuthProviderResponse[]> {
  const { baseUrl = apiBaseUrl } = options;
  const emailDomain = email.split("@")[1];
  const url = `${baseUrl}/auth/providers/?email_domain=${emailDomain}`;
  const { data } = await authenticatedFetch<
    PaginatedData<AuthProviderResponse[]>
  >(url);
  return data;
}

/**
 * Logs out the current user
 *
 * @param queryClient - the react query client whose cache is to be reset
 * @param appState - the app state which is to be cleared
 * @param options - other options for making the query
 */
export async function logout(
  queryClient: QueryClient,
  appState: AppState,
  options: { baseUrl?: string } = {}
) {
  const { baseUrl = apiBaseUrl } = options;
  appState.clear();
  queryClient.clear();
  await authenticatedFetch(`${baseUrl}/auth/logout`, { method: "post" });
}

/**
 * Deletes the token for the current user on the system
 * @param id of the token
 * @param options - extra options for querying the jobs
 *           - baseUrl - the API base URL; default apiBaseUrl
 */
export async function deleteMyToken(
  id: string,
  options: { baseUrl?: string } = {}
): Promise<void> {
  const { baseUrl = apiBaseUrl } = options;
  await authenticatedFetch(
    `${baseUrl}/me/tokens/${id}`,
    {
      method: "delete",
    },
    { isJsonOutput: false }
  );
}

/**
 * Deletes the project for the current user on the system
 * @param id of the project
 * @param options - extra options for querying the jobs
 *           - baseUrl - the API base URL; default apiBaseUrl
 */
export async function deleteMyProject(
  id: string,
  options: { baseUrl?: string } = {}
): Promise<void> {
  const { baseUrl = apiBaseUrl } = options;
  await authenticatedFetch(
    `${baseUrl}/me/projects/${id}`,
    {
      method: "delete",
    },
    { isJsonOutput: false }
  );
}

/**
 * Deletes the given project
 * @param id of the project
 * @param options - extra options for querying the jobs
 *           - baseUrl - the API base URL; default apiBaseUrl
 */
export async function deleteAdminProject(
  id: string,
  options: { baseUrl?: string } = {}
): Promise<void> {
  const { baseUrl = apiBaseUrl } = options;
  await authenticatedFetch(
    `${baseUrl}/admin/projects/${id}`,
    {
      method: "delete",
    },
    { isJsonOutput: false }
  );
}

/**
 * Updates the admin project
 * @param id - the id for the project
 * @param payload - the payload for the update
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function updateAdminProject(
  id: string,
  payload: UpdateProjectPutBody,
  options: {
    baseUrl?: string;
  } = {}
): Promise<AdminProject> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/admin/projects/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Creates a new project, when logged in as an admin
 *
 * @param payload - the payload for the creation
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function createAdminProject(
  payload: AdminCreateProjectBody,
  options: {
    baseUrl?: string;
  } = {}
): Promise<AdminProject> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/admin/projects/`, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Approves a user request
 *
 * @param id - the unique identifier of the user request
 * @param options - extra options e.g.
 *             - baseUrl - the API base URL; default apiBaseUrl
 */
export async function approveUserRequest(
  id: string,
  options: { baseUrl?: string } = {}
): Promise<UserRequest> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/admin/user-requests/${id}`, {
    method: "PUT",
    body: JSON.stringify({ status: UserRequestStatus.APPROVED }),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Rejects a user request
 *
 * @param id - the unique identifier of the user request
 * @param options - extra options e.g.
 *             - baseUrl - the API base URL; default apiBaseUrl
 */
export async function rejectUserRequest(
  id: string,
  options: { baseUrl?: string } = {}
): Promise<UserRequest> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/admin/user-requests/${id}`, {
    method: "PUT",
    body: JSON.stringify({ status: UserRequestStatus.REJECTED }),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Retrieves the devices on the system
 * @param baseUrl - the API base URL
 * @param skip - the number of records to skip in pagination
 * @param limit - the maximum number of records to return in pagination
 */
async function getDevices(
  baseUrl: string = apiBaseUrl,
  skip: number | null = null,
  limit: number | null = null
): Promise<Device[]> {
  const query = getQueryString({ skip, limit });
  const { data } = await authenticatedFetch<PaginatedData<Device[]>>(
    `${baseUrl}/devices/?${query}`
  );
  return data;
}

/**
 * Retrieve the given device on the system
 * @param name - the name of the device
 * @param baseUrl - the API base URL
 */
async function getDeviceDetail(
  name: string,
  baseUrl: string = apiBaseUrl
): Promise<Device> {
  return await authenticatedFetch(`${baseUrl}/devices/${name}`);
}

/**
 * Retrieve the user who is currently logged in on the system
 * @param baseUrl - the API base URL
 */
async function getCurrentUser(baseUrl: string = apiBaseUrl): Promise<User> {
  return await authenticatedFetch(`${baseUrl}/me`);
}

/**
 * Retrieves the calibration data for the devices on the system
 * @param baseUrl - the API base URL
 * @param skip - the number of records to skip in pagination
 * @param limit - the maximum number of records to return in pagination
 */
async function getCalibrations(
  baseUrl: string = apiBaseUrl,
  skip: number | null = null,
  limit: number | null = null
): Promise<DeviceCalibration[]> {
  const queryString = getQueryString({ skip, limit });
  const rawResult = await authenticatedFetch<
    PaginatedData<DeviceCalibration[]>
  >(`${baseUrl}/calibrations/?${queryString}`);
  return rawResult.data.map(normalizeCalibrationData);
}

/**
 * Retrieves the calibration data for the devices on the system
 * @param name - the name of the device
 * @param baseUrl - the API base URL
 */
async function getCalibrationsForDevice(
  name: string,
  baseUrl: string = apiBaseUrl
): Promise<DeviceCalibration> {
  const rawResult = await authenticatedFetch<DeviceCalibration>(
    `${baseUrl}/calibrations/${name}`
  );
  return normalizeCalibrationData(rawResult);
}

/**
 * Retrieves the jobs for the current user on the system
 * @param options - extra options for querying the jobs
 *      e.g. - project id
 *           - baseUrl - the API base URL; default apiBaseUrl
 */
async function getMyJobs(
  options: {
    project_id?: string;
    baseUrl?: string;
    skip?: number;
    limit?: number;
  } = {}
): Promise<Job[]> {
  const { project_id, skip, limit, baseUrl = apiBaseUrl } = options;
  const query = getQueryString({ skip, limit, project_id });
  const { data } = await authenticatedFetch<PaginatedData<Job[]>>(
    `${baseUrl}/me/jobs/?${query}`
  );
  return data;
}

/**
 * Retrieves the app tokens for the current user on the system
 * @param options - extra options for querying the app tokens
 *      e.g. - project external id
 *           - baseUrl - the API base URL; default apiBaseUrl
 */
async function getMyTokens(
  options: { project_ext_id?: string; baseUrl?: string } = {}
): Promise<AppToken[]> {
  const { project_ext_id, baseUrl = apiBaseUrl } = options;
  const query = getQueryString({ project_ext_id });
  const { data } = await authenticatedFetch<PaginatedData<AppToken[]>>(
    `${baseUrl}/me/tokens/?${query}`
  );
  return data;
}

/**
 * Retrieves the projects for the current user on the system
 * @param baseUrl - the API base URL
 * @param filters - the filters against which to match the projects
 */
async function getMyProjects(
  baseUrl: string = apiBaseUrl,
  filters: { [k: string]: string } = {}
): Promise<Project[]> {
  const queryString = getQueryString(filters);
  const { data } = await authenticatedFetch<PaginatedData<Project[]>>(
    `${baseUrl}/me/projects/?${queryString}`
  );
  return data;
}

/**
 * Retrieves the QPU time user requests for given project ID's
 * @param baseUrl - the API base URL
 * @param [projectIds=[]] - the ids of the projects whose requests are to be returned
 */
async function getProjectQpuTimeRequests(
  baseUrl: string = apiBaseUrl,
  projectIds: string[] = [],
  status?: UserRequestStatus
): Promise<QpuTimeExtensionUserRequest[]> {
  const queryString = getQueryString({ status, projectIds });
  const { data } = await authenticatedFetch<
    PaginatedData<QpuTimeExtensionUserRequest[]>
  >(`${baseUrl}/admin/qpu-time-requests/?${queryString}`);

  return data;
}

/**
 * Retrieves the QPU time user requests
 * @param baseUrl - the API base URL
 * @param options - extra options for filtering the requests
 *            - status - the status of the requests
 *            - skip - the number of records to skip
 *            - limit - the maximum number of records to return
 */
async function getUserRequests(
  baseUrl: string = apiBaseUrl,
  options: {
    status?: UserRequestStatus;
    skip?: number;
    limit?: number;
  }
): Promise<UserRequest[]> {
  const queryString = getQueryString(options);
  const { data } = await authenticatedFetch<PaginatedData<UserRequest[]>>(
    `${baseUrl}/admin/user-requests/?${queryString}`
  );

  return data;
}

/**
 * Retrieves the projects in admin view
 * @param baseUrl - the API base URL
 * @param options - extra options for filtering the requests
 *            - is_active - whether the project is active or not
 *            - skip - the number of records to skip
 *            - limit - the maximum number of records to return
 */
async function getAdminProjects(
  baseUrl: string = apiBaseUrl,
  options: {
    is_active?: boolean;
    skip?: number;
    limit?: number;
  }
): Promise<AdminProject[]> {
  const queryString = getQueryString(options);
  const { data } = await authenticatedFetch<PaginatedData<AdminProject[]>>(
    `${baseUrl}/admin/projects/?${queryString}`
  );

  return data;
}

/**
 * Retrieves the bookings
 * @param baseUrl - the API base URL
 * @param backend - the backend from which to get the bookings
 * @param options - extra options for filtering the requests
 *            - min_start_utc - the minimum start_utc timestamp
 *            - max_start_utc - the maximum start_utc timestamp
 *            - user_id - the id of the user who owns the booking
 *            - skip - the number of records to skip
 *            - limit - the maximum number of records to return
 */
async function getBookingsOfBackend(
  baseUrl: string = apiBaseUrl,
  backend: string,
  options: {
    user_id?: string;
    min_start_utc?: string;
    max_start_utc?: string;
    skip?: string;
    limit?: string;
  }
): Promise<Booking[]> {
  const queryString = getQueryString(options);
  const { data } = await authenticatedFetch<PaginatedData<Booking[]>>(
    `${baseUrl}/bookings/${backend}?${queryString}`
  );

  return data;
}

/**
 * Extracts the error from the response
 *
 * @param response - the response from which to extract the error message
 */
async function extractError(response: Response): Promise<ErrorInfo> {
  let message = "unknown http error";
  try {
    const data = await response.clone().json();
    message = data["detail"] || JSON.stringify(data);
  } catch (error) {
    message = await response.text();
  }

  const error = new Error(message) as ErrorInfo;
  error.status = response.status;
  return error;
}

/**
 * Converts a map of query parameters into a query string starting with ?
 *
 * query params that are lists are converted to something like 'q=foo&q=bar&q=me'
 *
 * @param queryParams - the map of query parameters
 */
function getQueryString(queryParams: { [key: string]: unknown }): string {
  const definedQueryParams = Object.entries(queryParams)
    .filter(([_, value]) => value != null)
    .map(([k, v]) =>
      // expand values that are lists into individual key-value pairs
      Array.isArray(v) ? v.map((item) => [k, `${item}`]) : [[k, `${v}`]]
    )
    .flat();

  return new URLSearchParams(definedQueryParams).toString();
}

/**
 * A wrapper around the fetch functionality that adds
 * authentication in it
 *
 * @param input - the input to be passed to fetch
 * @param init - the init object to  pass to fetch
 * @param options - the extra options that are not passed to fetch
 *            - isJsonOutput: whether the output is JSON or not
 * @returns - the response from the backend
 */
async function authenticatedFetch<T>(
  input: string | URL | globalThis.Request,
  init: RequestInit = {},
  options: { isJsonOutput?: boolean } = {}
): Promise<T> {
  const response = await fetch(input, {
    ...init,
    credentials: "include",
  });

  if (response.ok) {
    const { isJsonOutput = true } = options;
    return isJsonOutput ? await response.json() : await response.text();
  }

  throw await extractError(response);
}
