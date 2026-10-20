import {
  keepPreviousData,
  QueryClient,
  queryOptions,
} from "@tanstack/react-query";
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
  User,
  UserRequestStatus,
  UserRequestType,
  UserRequest,
  UserRole,
  AdminProject,
  UpdateProjectPutBody,
  AdminCreateProjectBody,
  Booking,
  NewBookingInfo,
  GeneralMessage,
  BookingsConfig,
  RawBooking,
  RecalibrationInfo,
  Notice,
  NoticePostRequest,
  CountResponse,
  NoticePreferences,
  NoticeType,
  UserRequestPostBody,
} from "../../types";
import {
  normalizeCalibrationData,
  extendAppToken,
  toClientSideBooking,
} from "./utils";
import { DateTime } from "luxon";

export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
export const refetchInterval = parseFloat(
  import.meta.env.VITE_REFETCH_INTERVAL_MS || "120000",
); // default: 2 minutes

/**
 * the devices query for using with react query
 */
export const devicesQuery = queryOptions({
  queryKey: [apiBaseUrl, "devices"],
  queryFn: async () => await getDevices(apiBaseUrl),
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
  options: { baseUrl?: string } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  return queryOptions({
    queryKey: [baseUrl, "devices", name],
    queryFn: async () => await getDeviceDetail(name, baseUrl),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * the devices query for using with react query
 */
export const calibrationsQuery = queryOptions({
  queryKey: [apiBaseUrl, "calibrations"],
  queryFn: async () => await getCalibrations(apiBaseUrl),
  refetchInterval,
  throwOnError: true,
});

/**
 * the devices query for using with react query
 */
export const currentUserQuery = queryOptions({
  queryKey: [apiBaseUrl, "me"],
  queryFn: async () => await getCurrentUser(apiBaseUrl),
  throwOnError: true,
});

/**
 * the single device's calibration query for using with react query
 * @param options - extra options for filtering
 *          - baseUrl - the base URL of the API
 */
export function singleDeviceCalibrationQuery(
  name: string,
  options: { baseUrl?: string } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  return queryOptions({
    queryKey: [baseUrl, "calibrations", name],
    queryFn: async () => await getCalibrationsForDevice(name, baseUrl),
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
  options: { project_id?: string; baseUrl?: string } = {},
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
 *            - project_id - the ID of the tokens' project
 *            - projectList - List of all available projects
 */
export function myTokensQuery(options: {
  project_id?: string;
  projectList: Project[];
  baseUrl?: string;
}) {
  const { project_id, projectList, baseUrl = apiBaseUrl } = options;
  const queryKey = [baseUrl, "me", "tokens", project_id];

  return queryOptions({
    queryKey,
    queryFn: async () => {
      const rawTokens = await getMyTokens({ project_id });
      const projectMap: { [k: string]: Project } = Object.fromEntries(
        projectList.map((v) => [v.id, { ...v }]),
      );

      return rawTokens
        .map(
          (v) =>
            projectMap[v.project_id] &&
            extendAppToken(v, projectMap[v.project_id]),
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
 * the react query for getting all the user requests awaiting an admin
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
  const queryKey = [baseUrl, "me", "requests", "approver", status, limit, skip];
  // run only for admins
  const enabled = currentUser.roles.includes(UserRole.ADMIN);

  return queryOptions({
    queryKey,
    queryFn: async () =>
      await getMyRequests(baseUrl, { role: "approver", status, limit, skip }),
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
  const queryKey = [baseUrl, "admin", "projects", is_active, limit, skip];
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
 * the query for getting the current user's qpu time requests for my projects using with react query
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
  const types = [UserRequestType.PROJECT_QPU_SECONDS];
  const queryKey = [baseUrl, "me", "requests", "requester", status, types];

  return queryOptions({
    queryKey: [...queryKey, projectIds],
    queryFn: async () => {
      const data = await getMyRequests(baseUrl, {
        role: "requester",
        status,
        types,
      });
      return data.filter((v) => projectIds.includes(v.resource_id));
    },
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * the react query for getting upcoming bookings of given backend
 *
 * @param options - extra options for filtering the requests
 *            - baseUrl - the base URL of the API
 *            - backend - the name of the device where the bookings are
 *            - user_id - the ID of the user whose bookings ar eto be got
 *            - max_start_utc - the maximum start UTC datetime for getting a range of bookings
 *            - skip - the number of records to skip; default = 0
 *            - limit - the maximum number of records to return; default = '5'
 *           - throwOnError - whether to throw on error or not; default = true
 */
export function upcomingBookingsQuery(options: {
  backend: string;
  baseUrl?: string;
  user_id?: string;
  max_start_utc?: string;
  skip?: string;
  limit?: string;
  throwOnError?: boolean;
}) {
  // by default, we get the upcoming 5 events tops per backend (i.e. limit = '5')
  const {
    baseUrl = apiBaseUrl,
    skip = "0",
    backend,
    limit = "5",
    throwOnError = true,
    user_id,
    max_start_utc,
  } = options;
  // Ensure that the query key does not depend on the min_start_utc as
  // that is always shifting on every refresh
  const queryKey = [
    baseUrl,
    "bookings",
    backend,
    user_id,
    "upcoming",
    max_start_utc,
    limit,
    skip,
  ];

  return queryOptions({
    queryKey,
    queryFn: async () =>
      await getFutureBookings(baseUrl, backend, {
        user_id,
        max_start_utc,
        limit,
        skip,
      }),
    refetchInterval,
    throwOnError,
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
  sort?: string[];
}) {
  const {
    baseUrl = apiBaseUrl,
    skip = "0",
    backend,
    limit,
    user_id,
    min_start_utc,
    max_start_utc,
    sort,
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
    sort,
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
        sort,
      }),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * the single device query for using with react query
 * @param backend - the name of the device to consider
 * @param options - extra options for filtering
 *          - baseUrl - the base URL of the API
 */
export function bookingsConfigQuery(
  backend: string,
  options: { baseUrl?: string } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  return queryOptions({
    queryKey: [baseUrl, "bookings", backend, "config"],
    queryFn: async () => await getBookingsConfig(backend, baseUrl),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * the notices query for using with react query
 * @param options - extra options for filtering
 *          - baseUrl - the base URL of the API
 *          - user_id: The IDs of the users to retrieve notices for
 *          - min_start_utc: The minimum UTC timestamp the notice should start
 *          - max_start_utc: The maximum UTC timestamp the notice should start
 *          - min_expires_utc: The minimum UTC timestamp the notice should expire
 *          - max_expires_utc: The maximum UTC timestamp the notice should expire
 *          - include_dismissed: whether to include dismissed notices
 *          - skip: the number of records to skip
 *          - limit: the maximum number of records to return
 *          - sort: the fields to sort by
 */
export function noticesQuery(
  options: {
    baseUrl?: string;
    types?: NoticeType[];
    user_id?: string;
    min_start_utc?: string;
    max_start_utc?: string;
    min_expires_utc?: string;
    max_expires_utc?: string;
    include_dismissed?: boolean;
    skip?: number;
    limit?: number;
    sort?: string[];
  } = {},
) {
  const { baseUrl = apiBaseUrl, ...rest } = options;
  const {
    types,
    user_id,
    min_start_utc,
    max_start_utc,
    min_expires_utc,
    max_expires_utc,
    include_dismissed,
    skip,
    limit,
    sort,
  } = rest;
  const queryKey = [
    baseUrl,
    "admin",
    "notices",
    types,
    user_id,
    min_start_utc,
    max_start_utc,
    min_expires_utc,
    max_expires_utc,
    include_dismissed,
    limit,
    skip,
    sort,
  ];
  return queryOptions({
    queryKey: queryKey,
    queryFn: async () => await getNotices(baseUrl, rest),
    refetchInterval,
    throwOnError: true,
    placeholderData: keepPreviousData,
  });
}

/**
 * the notice count query
 * @param options - extra options for filtering
 *          - baseUrl - the base URL of the API
 *          - types: the notice types to count
 *          - is_read: filter on read state; omit for either
 *          - user_id: The IDs of the users to retrieve notices for
 *          - min_start_utc: The minimum UTC timestamp the notice should start
 *          - max_start_utc: The maximum UTC timestamp the notice should start
 *          - min_expires_utc: The minimum UTC timestamp the notice should expire
 *          - max_expires_utc: The maximum UTC timestamp the notice should expire
 *          - include_dismissed: whether to include dismissed notices
 */
export function noticeCountQuery(
  options: {
    baseUrl?: string;
    types?: NoticeType[];
    is_read?: boolean;
    user_id?: string;
    min_start_utc?: string;
    max_start_utc?: string;
    min_expires_utc?: string;
    max_expires_utc?: string;
    include_dismissed?: boolean;
  } = {},
) {
  const { baseUrl = apiBaseUrl, ...rest } = options;
  const {
    types,
    is_read,
    user_id,
    min_start_utc,
    max_start_utc,
    min_expires_utc,
    max_expires_utc,
    include_dismissed,
  } = rest;
  const queryKey = [
    baseUrl,
    "counts",
    "notices",
    types,
    is_read,
    user_id,
    min_start_utc,
    max_start_utc,
    min_expires_utc,
    max_expires_utc,
    include_dismissed,
  ];
  return queryOptions({
    queryKey: queryKey,
    queryFn: async () => await getNoticeCount(baseUrl, rest),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * React Query wrapper around getRecalibrationInfo
 *
 * @param backend - the name of the backend device
 * @param options - extra options e.g. baseUrl
 */
export function recalibrationInfoQuery(
  backend: string,
  options: { baseUrl?: string } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  return queryOptions({
    queryKey: [baseUrl, "admin", "recalibration", backend, "info"],
    queryFn: async () => await getRecalibrationInfo(backend, { baseUrl }),
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
  } = {},
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
  } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({
    queryKey: [baseUrl, "me", "projects"],
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
  } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({ queryKey: [baseUrl, "admin"] });
}

/**
 * Refreshes the queries for the bookings of a given backend from the API
 *
 * @param queryClient - the query client for making queries
 * @param  backend - the name of the device
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function refreshBookingsQueries(
  queryClient: QueryClient,
  backend: string,
  options: {
    baseUrl?: string;
  } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({
    queryKey: [baseUrl, "bookings", backend],
  });
}

/**
 * Refreshes all notices cache
 * @param queryClient - the query client for making queries
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function refreshAllNotices(
  queryClient: QueryClient,
  options: {
    baseUrl?: string;
  } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({
    queryKey: [baseUrl, "admin", "notices"],
  });
}

/**
 * Refreshes all notice count cache
 * @param queryClient - the query client for making queries
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function refreshAllNoticeCounts(
  queryClient: QueryClient,
  options: {
    baseUrl?: string;
  } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({
    queryKey: [baseUrl, "counts", "notices"],
  });
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
  } = {},
): Promise<AppTokenCreationResponse> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/me/tokens/`, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Cancels the booking of the given id for the given backend
 *
 * @param backend - the name of the device
 * @param id of the booking
 * @param options - extra options:
 *           - baseUrl - the API base URL; default apiBaseUrl
 */
export async function cancelBooking(
  backend: string,
  id: string,
  options: { baseUrl?: string } = {},
): Promise<GeneralMessage> {
  const { baseUrl = apiBaseUrl } = options;
  const resp: GeneralMessage = await authenticatedFetch(
    `${baseUrl}/bookings/${backend}/${id}/cancel`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    },
  );
  if (resp.status !== "success") {
    const errMsg = `${resp.status}: ${resp.detail}`;
    const err = new Error(errMsg) as ErrorInfo;
    err.statusText = resp.status;
    throw err;
  }

  return resp;
}

/**
 * Updates the booking in the given backend
 * @param backend - the name of the device
 * @param id - the id for the booking
 * @param payload - the payload for the update
 * @param options - the options including:
 *          - baseUrl - the base URL of the API
 */
export async function updateBooking(
  backend: string,
  id: string,
  payload: NewBookingInfo,
  options: {
    baseUrl?: string;
  } = {},
): Promise<Booking> {
  const { baseUrl = apiBaseUrl } = options;
  await cancelBooking(backend, id, { baseUrl });
  return await createNewBooking(backend, payload, { baseUrl });
}

/**
 * Generates a new booking
 * @param backend - the name of the device
 * @param payload - the payload for a new booking
 * @param options - the options:
 *          - baseUrl - the base URL of the API
 *          - backend - the name of the backend
 */
export async function createNewBooking(
  backend: string,
  payload: NewBookingInfo,
  options: {
    baseUrl?: string;
  } = {},
): Promise<Booking> {
  const { baseUrl = apiBaseUrl } = options;
  const record = await authenticatedFetch<RawBooking>(
    `${baseUrl}/bookings/${backend}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json" },
    },
  );
  return toClientSideBooking(record, { backend });
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
  } = {},
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
  } = {},
): Promise<UserRequest> {
  const { baseUrl = apiBaseUrl } = options;
  const { project_id, seconds, reason } = payload;
  const body: UserRequestPostBody = {
    type: UserRequestType.PROJECT_QPU_SECONDS,
    resource_id: project_id,
    reason,
    metadata: { seconds },
  };
  return await authenticatedFetch(`${baseUrl}/me/requests/`, {
    method: "POST",
    body: JSON.stringify(body),
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
  } = {},
): Promise<AuthProviderResponse[]> {
  const { baseUrl = apiBaseUrl } = options;
  const emailDomain = email.split("@")[1];
  const url = `${baseUrl}/auth/providers/?email_domain=${emailDomain}`;
  const { data } =
    await authenticatedFetch<PaginatedData<AuthProviderResponse[]>>(url);
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
  options: { baseUrl?: string } = {},
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
  options: { baseUrl?: string } = {},
): Promise<void> {
  const { baseUrl = apiBaseUrl } = options;
  await authenticatedFetch(
    `${baseUrl}/me/tokens/${id}`,
    {
      method: "delete",
    },
    { isJsonOutput: false },
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
  options: { baseUrl?: string } = {},
): Promise<void> {
  const { baseUrl = apiBaseUrl } = options;
  await authenticatedFetch(
    `${baseUrl}/me/projects/${id}`,
    {
      method: "delete",
    },
    { isJsonOutput: false },
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
  options: { baseUrl?: string } = {},
): Promise<void> {
  const { baseUrl = apiBaseUrl } = options;
  await authenticatedFetch(
    `${baseUrl}/admin/projects/${id}`,
    {
      method: "delete",
    },
    { isJsonOutput: false },
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
  } = {},
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
  } = {},
): Promise<AdminProject> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/admin/projects/`, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Starts a recalibration cycle
 *
 * @param backend - the name of the backend
 * @param options - extra options e.g.
 *             - baseUrl - the API base URL; default apiBaseUrl
 *             - interval - the interval at which to repeat the recalibration
 *             - start_timestamp - the timestamp when the cycle should start
 */
export async function startRecalibration(
  backend: string,
  options: {
    baseUrl?: string;
    interval?: number;
    start_timestamp?: string;
  } = {},
): Promise<UserRequest> {
  const { baseUrl = apiBaseUrl, ...rest } = options;
  const query = getQueryString(rest);
  return await authenticatedFetch(
    `${baseUrl}/admin/bcc/recalibration/${backend}/init?${query}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    },
  );
}

/**
 * Gets recalibration information
 *
 * @param backend - the name of the backend
 * @param options - extra options e.g.
 *             - baseUrl - the API base URL; default apiBaseUrl
 */
export async function getRecalibrationInfo(
  backend: string,
  options: { baseUrl?: string } = {},
): Promise<RecalibrationInfo> {
  const { baseUrl = apiBaseUrl, ...rest } = options;
  const query = getQueryString(rest);
  return await authenticatedFetch(
    `${baseUrl}/admin/bcc/recalibration/${backend}/info?${query}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    },
  );
}

/**
 * Stops a recalibration cycle
 *
 * @param backend - the name of the backend
 * @param options - extra options e.g.
 *             - baseUrl - the API base URL; default apiBaseUrl
 *             - ignore_errors - whether to ignore errors when stopping recalibration or not
 */
export async function stopRecalibration(
  backend: string,
  options: { baseUrl?: string; ignore_errors?: boolean } = {},
): Promise<UserRequest> {
  const { baseUrl = apiBaseUrl, ...rest } = options;
  const query = getQueryString(rest);
  return await authenticatedFetch(
    `${baseUrl}/admin/bcc/recalibration/${backend}/cancel?${query}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    },
  );
}

/**
 * Sets a backend device online
 *
 * @param backend - the name of the backend
 * @param options - extra options e.g. baseUrl
 */
export async function switchBackendOn(
  backend: string,
  options: { baseUrl?: string } = {},
): Promise<GeneralMessage> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/admin/bcc/switch/${backend}/on`, {
    method: "POST",
  });
}

/**
 * Sets a backend device offline
 *
 * @param backend - the name of the backend
 * @param options - extra options e.g. baseUrl
 */
export async function switchBackendOff(
  backend: string,
  options: { baseUrl?: string } = {},
): Promise<GeneralMessage> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/admin/bcc/switch/${backend}/off`, {
    method: "POST",
    body: JSON.stringify({ is_online: false }),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Retrieves notices
 *
 * @param options - extra options e.g.
 *          - baseUrl: The base URL of the API
 *          - types: the notice types to retrieve
 *          - user_id: The IDs of the users to retrieve notices for
 *          - min_start_utc: The minimum UTC timestamp the notice should start
 *          - max_start_utc: The maximum UTC timestamp the notice should start
 *          - min_expires_utc: The minimum UTC timestamp the notice should expire
 *          - max_expires_utc: The maximum UTC timestamp the notice should expire
 *          - include_dismissed: whether to include dismissed notices
 *          - skip: the number of records to skip
 *          - limit: the maximum number of records to return
 *          - sort: the fields to sort by
 */
export async function getNotices(
  baseUrl: string = apiBaseUrl,
  options: {
    types?: NoticeType[];
    user_id?: string;
    min_start_utc?: string;
    max_start_utc?: string;
    min_expires_utc?: string;
    max_expires_utc?: string;
    include_dismissed?: boolean;
    skip?: number;
    limit?: number;
    sort?: string[];
  } = {},
): Promise<Notice[]> {
  const { types, ...rest } = options;
  const queryString = getQueryString({ ...rest, type: types });
  const { data } = await authenticatedFetch<PaginatedData<Notice[]>>(
    `${baseUrl}/admin/notices?${queryString}`,
  );
  return data;
}

/**
 * Retrieves the number of notices that fulfill some criteria
 *
 * @param options - extra options e.g.
 *          - baseUrl: The base URL of the API
 *          - types: the notice types to count
 *          - is_read: filter on read state; omit for either
 *          - user_id: The IDs of the users to retrieve notices for
 *          - min_start_utc: The minimum UTC timestamp the notice should start
 *          - max_start_utc: The maximum UTC timestamp the notice should start
 *          - min_expires_utc: The minimum UTC timestamp the notice should expire
 *          - max_expires_utc: The maximum UTC timestamp the notice should expire
 *          - include_dismissed: whether to include dismissed notices
 */
export async function getNoticeCount(
  baseUrl: string = apiBaseUrl,
  options: {
    types?: NoticeType[];
    is_read?: boolean;
    user_id?: string;
    min_start_utc?: string;
    max_start_utc?: string;
    min_expires_utc?: string;
    max_expires_utc?: string;
    include_dismissed?: boolean;
  } = {},
): Promise<number> {
  const { types, ...rest } = options;
  const queryString = getQueryString({ ...rest, type: types });
  const { count } = await authenticatedFetch<CountResponse>(
    `${baseUrl}/counts/notices?${queryString}`,
  );
  return count;
}

/**
 * Creates a notice for a given set of users or all users
 *
 * @param payload - the notice fields
 * @param options - extra options e.g. baseUrl
 * @returns one notice per targeted user, or the one notice for all users
 */
export async function createNotice(
  payload: NoticePostRequest,
  options: { baseUrl?: string } = {},
): Promise<Notice[]> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/admin/notices/`, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Deletes a notice for all users
 *
 * @param id - the notice ID
 * @param options - extra options e.g. baseUrl
 */
export async function deleteNotice(
  id: string,
  options: { baseUrl?: string } = {},
): Promise<void> {
  const { baseUrl = apiBaseUrl } = options;
  await authenticatedFetch(
    `${baseUrl}/admin/notices/${id}`,
    {
      method: "DELETE",
    },
    { isJsonOutput: false },
  );
}

/**
 * Marks one of the current user's notices read
 *
 * @param id - the notice ID
 * @param options - extra options e.g. baseUrl
 */
export async function dismissNotice(
  id: string,
  options: { baseUrl?: string } = {},
): Promise<GeneralMessage> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/me/notices/${id}/dismiss`, {
    method: "POST",
  });
}

/**
 * Marks every one of the current user's notices read
 *
 * @param options - extra options e.g. baseUrl
 */
export async function dismissAllMyNotices(
  options: { baseUrl?: string } = {},
): Promise<GeneralMessage> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/me/notices/dismiss`, {
    method: "POST",
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
  limit: number | null = null,
): Promise<Device[]> {
  const query = getQueryString({ skip, limit });
  const { data } = await authenticatedFetch<PaginatedData<Device[]>>(
    `${baseUrl}/devices/?${query}`,
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
  baseUrl: string = apiBaseUrl,
): Promise<Device> {
  return await authenticatedFetch(`${baseUrl}/devices/${name}`);
}

/**
 * Retrieve the bookings config for the given backend
 * @param backend - the name of the device
 * @param baseUrl - the API base URL
 */
async function getBookingsConfig(
  backend: string,
  baseUrl: string = apiBaseUrl,
): Promise<BookingsConfig> {
  return await authenticatedFetch(`${baseUrl}/bookings/${backend}/config`);
}

/**
 * Retrieve the user who is currently logged in on the system
 * @param baseUrl - the API base URL
 */
async function getCurrentUser(baseUrl: string = apiBaseUrl): Promise<User> {
  return await authenticatedFetch(`${baseUrl}/me/profile`);
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
  limit: number | null = null,
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
  baseUrl: string = apiBaseUrl,
): Promise<DeviceCalibration> {
  const rawResult = await authenticatedFetch<DeviceCalibration>(
    `${baseUrl}/calibrations/${name}`,
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
  } = {},
): Promise<Job[]> {
  const { project_id, skip, limit, baseUrl = apiBaseUrl } = options;
  const query = getQueryString({ skip, limit, project_id });
  const { data } = await authenticatedFetch<PaginatedData<Job[]>>(
    `${baseUrl}/me/jobs/?${query}`,
  );
  return data;
}

/**
 * Retrieves the app tokens for the current user on the system
 * @param options - extra options for querying the app tokens
 *      e.g. - project id
 *           - baseUrl - the API base URL; default apiBaseUrl
 */
async function getMyTokens(
  options: { project_id?: string; baseUrl?: string } = {},
): Promise<AppToken[]> {
  const { project_id, baseUrl = apiBaseUrl } = options;
  const query = getQueryString({ project_id });
  const { data } = await authenticatedFetch<PaginatedData<AppToken[]>>(
    `${baseUrl}/me/tokens/?${query}`,
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
  filters: { [k: string]: string } = {},
): Promise<Project[]> {
  const queryString = getQueryString(filters);
  const { data } = await authenticatedFetch<PaginatedData<Project[]>>(
    `${baseUrl}/me/projects/?${queryString}`,
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
  },
): Promise<AdminProject[]> {
  const queryString = getQueryString(options);
  const { data } = await authenticatedFetch<PaginatedData<AdminProject[]>>(
    `${baseUrl}/admin/projects/?${queryString}`,
  );

  return data;
}

/**
 * Retrieves the bookings that are always in the future
 * @param baseUrl - the API base URL
 * @param backend - the backend from which to get the bookings
 * @param options - extra options for filtering the requests
 *            - max_start_utc - the maximum start_utc timestamp
 *            - user_id - the id of the user who owns the booking
 *            - skip - the number of records to skip
 *            - limit - the maximum number of records to return
 */
async function getFutureBookings(
  baseUrl: string = apiBaseUrl,
  backend: string,
  options: {
    user_id?: string;
    max_start_utc?: string;
    skip?: string;
    limit?: string;
  },
): Promise<Booking[]> {
  const min_start_utc = DateTime.utc().toISO();
  return await getBookingsOfBackend(baseUrl, backend, {
    ...options,
    min_start_utc,
  });
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
 *            - sort - the list of fields to sort by; prepending "-" means return records in descending values of field
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
    sort?: string[];
  },
): Promise<Booking[]> {
  const queryString = getQueryString(options);
  const { data } = await authenticatedFetch<PaginatedData<RawBooking[]>>(
    `${baseUrl}/bookings/${backend}?${queryString}`,
  );

  return data.map((v) => toClientSideBooking(v, { backend }));
}


/**
 * the query for the current user's notices, newest first
 *
 * @param options - extra options for filtering
 *          - baseUrl - the base URL of the API
 *          - types - the notice types to include
 *          - is_read - filter on read state; omit for either
 *          - skip - the number of records to skip
 *          - limit - the maximum number of records to return
 */
export function myNoticesQuery(
  options: {
    baseUrl?: string;
    types?: NoticeType[];
    is_read?: boolean;
    skip?: number;
    limit?: number;
  } = {},
) {
  const { baseUrl = apiBaseUrl, ...rest } = options;
  const { types, is_read, skip, limit } = rest;
  return queryOptions({
    queryKey: [baseUrl, "me", "notices", types, is_read, skip, limit],
    queryFn: async () => await getMyNotices(baseUrl, rest),
    // no polling: the count badge below is what needs to stay fresh, and the list
    // refetches when the panel opens and after any reaction
    throwOnError: true,
    placeholderData: keepPreviousData,
  });
}

/**
 * the query for which notice types the current user also gets by email
 *
 * @param options - extra options e.g. baseUrl
 */
export function noticePreferencesQuery(options: { baseUrl?: string } = {}) {
  const { baseUrl = apiBaseUrl } = options;
  return queryOptions({
    queryKey: [baseUrl, "me", "notices", "preferences"],
    queryFn: async () => await getNoticePreferences(baseUrl),
    throwOnError: true,
  });
}

/**
 * the query for the requests the current user made, or those awaiting their approval
 *
 * @param options - extra options for filtering
 *          - baseUrl - the base URL of the API
 *          - role - whether to return the user's own requests or ones they may react to
 *          - status - the status to filter by
 *          - types - the request types to filter by
 */
export function myRequestsQuery(
  options: {
    baseUrl?: string;
    role?: "requester" | "approver";
    status?: UserRequestStatus;
    types?: UserRequestType[];
  } = {},
) {
  const { baseUrl = apiBaseUrl, ...rest } = options;
  const { role = "requester", status, types } = rest;
  return queryOptions({
    queryKey: [baseUrl, "me", "requests", role, status, types],
    queryFn: async () => await getMyRequests(baseUrl, { ...rest, role }),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * Refreshes the queries for the current user's notices and all notice counts
 *
 * @param queryClient - the query client for making queries
 * @param options - the options including baseUrl
 */
export async function refreshMyNotices(
  queryClient: QueryClient,
  options: { baseUrl?: string } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({ queryKey: [baseUrl, "me", "notices"] });
  await refreshAllNoticeCounts(queryClient, { baseUrl });
}

/**
 * Refreshes the queries for the current user's requests, either role
 *
 * @param queryClient - the query client for making queries
 * @param options - the options including baseUrl
 */
export async function refreshMyRequests(
  queryClient: QueryClient,
  options: { baseUrl?: string } = {},
) {
  const { baseUrl = apiBaseUrl } = options;
  await queryClient.invalidateQueries({ queryKey: [baseUrl, "me", "requests"] });
}

/**
 * Requests access to an existing shared project, by its ID
 *
 * @param payload - the project ID and the reason for asking
 * @param options - extra options e.g. baseUrl
 */
export async function requestProjectAccess(
  payload: { project_id: string; reason: string },
  options: { baseUrl?: string } = {},
): Promise<UserRequest> {
  const { baseUrl = apiBaseUrl } = options;
  const body: UserRequestPostBody = {
    type: UserRequestType.PROJECT_ACCESS,
    resource_id: payload.project_id,
    reason: payload.reason,
  };
  return await authenticatedFetch(`${baseUrl}/me/requests/`, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Approves a request the current user is entitled to react to
 *
 * @param id - the unique identifier of the request
 * @param options - extra options e.g. baseUrl
 */
export async function approveMyRequest(
  id: string,
  options: { baseUrl?: string } = {},
): Promise<UserRequest> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/me/requests/${id}`, {
    method: "PUT",
    body: JSON.stringify({ status: UserRequestStatus.APPROVED }),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Rejects a request the current user is entitled to react to
 *
 * @param args - the request id and the optional reason for rejecting
 * @param options - extra options e.g. baseUrl
 */
export async function rejectMyRequest(
  args: { id: string; reason?: string },
  options: { baseUrl?: string } = {},
): Promise<UserRequest> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/me/requests/${args.id}`, {
    method: "PUT",
    body: JSON.stringify({
      status: UserRequestStatus.REJECTED,
      rejection_reason: args.reason,
    }),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Updates whether the named notice types are also emailed, leaving the rest untouched
 *
 * @param payload - the types to change and whether to email them
 * @param options - extra options e.g. baseUrl
 */
export async function updateNoticePreferences(
  payload: Partial<NoticePreferences>,
  options: { baseUrl?: string } = {},
): Promise<NoticePreferences> {
  const { baseUrl = apiBaseUrl } = options;
  return await authenticatedFetch(`${baseUrl}/me/notices/preferences/`, {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Removes a member from a project the current user administers
 *
 * @param args - the project id and the member's user id
 * @param options - extra options e.g. baseUrl
 */
export async function removeProjectMember(
  args: { projectId: string; userId: string },
  options: { baseUrl?: string } = {},
): Promise<void> {
  const { baseUrl = apiBaseUrl } = options;
  await authenticatedFetch(
    `${baseUrl}/me/projects/${args.projectId}/members/${args.userId}`,
    { method: "DELETE" },
    { isJsonOutput: false },
  );
}

/**
 * the query for user email addresses, for completing the admin project forms
 *
 * @param options - extra options for filtering
 *          - baseUrl - the base URL of the API
 *          - search - a case-insensitive substring of the address
 */
export function userEmailsQuery(
  options: { baseUrl?: string; search?: string } = {},
) {
  const { baseUrl = apiBaseUrl, search } = options;
  return queryOptions({
    queryKey: [baseUrl, "admin", "user-emails", search],
    queryFn: async () => await getUserEmails(baseUrl, search),
    // a directory of addresses does not go stale in the life of a form, and the list
    // must not blank while the next search is in flight
    staleTime: 5 * 60_000,
    placeholderData: keepPreviousData,
  });
}

/**
 * Retrieves user email addresses, superuser only
 *
 * @param baseUrl - the API base URL
 * @param search - a case-insensitive substring of the address
 */
async function getUserEmails(
  baseUrl: string = apiBaseUrl,
  search?: string,
): Promise<string[]> {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  return await authenticatedFetch(`${baseUrl}/admin/users/emails/${query}`, {
    method: "GET",
  });
}

/**
 * Retrieves the current user's notices, newest first
 * @param baseUrl - the API base URL
 * @param options - extra options for filtering
 */
async function getMyNotices(
  baseUrl: string = apiBaseUrl,
  options: {
    types?: NoticeType[];
    is_read?: boolean;
    skip?: number;
    limit?: number;
  } = {},
): Promise<Notice[]> {
  const { types, ...rest } = options;
  const queryString = getQueryString({ ...rest, type: types });
  const { data } = await authenticatedFetch<PaginatedData<Notice[]>>(
    `${baseUrl}/me/notices/?${queryString}`,
  );
  return data;
}

/**
 * Retrieves which notice types the current user also gets by email
 * @param baseUrl - the API base URL
 */
async function getNoticePreferences(
  baseUrl: string = apiBaseUrl,
): Promise<NoticePreferences> {
  return await authenticatedFetch(`${baseUrl}/me/notices/preferences/`);
}

/**
 * Retrieves the requests the current user made, or those awaiting their approval
 * @param baseUrl - the API base URL
 * @param options - extra options for filtering
 */
async function getMyRequests(
  baseUrl: string = apiBaseUrl,
  options: {
    role?: "requester" | "approver";
    status?: UserRequestStatus;
    types?: UserRequestType[];
    skip?: number;
    limit?: number;
  } = {},
): Promise<UserRequest[]> {
  const { types, ...rest } = options;
  const queryString = getQueryString({ ...rest, type: types });
  const { data } = await authenticatedFetch<PaginatedData<UserRequest[]>>(
    `${baseUrl}/me/requests/?${queryString}`,
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
      Array.isArray(v) ? v.map((item) => [k, `${item}`]) : [[k, `${v}`]],
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
  options: { isJsonOutput?: boolean } = {},
): Promise<T> {
  const response = await fetch(input, {
    ...init,
    credentials: "include",
  });

  if (response.ok) {
    const { isJsonOutput = true } = options;
    // @ts-ignore
    return isJsonOutput ? await response.json() : await response.text();
  }

  throw await extractError(response);
}
