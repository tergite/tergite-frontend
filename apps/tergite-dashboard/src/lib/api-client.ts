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
  type AppToken,
  type AppTokenUpdateRequest,
  QpuTimeExtensionPostBody,
  User,
  UserRequestStatus,
  UserRequestType,
  UserRequest,
  type ExtendedUserRequest,
  UserRole,
  AdminProject,
  UpdateProjectPutBody,
  AdminCreateProjectBody,
  Booking,
  NewBookingInfo,
  GeneralMessage,
  BookingsConfig,
  RawBooking,
  UserRequestMetadata,
  RecalibrationInfo,
  Notice,
  NoticePostRequest,
  NoticePreferences,
  NoticeType,
} from "../../types";
import {
  normalizeCalibrationData,
  extendAppToken,
  extendUserRequest,
  toClientSideBooking,
} from "./utils";
import { DateTime } from "luxon";
import { client } from "./api/client";

export const refetchInterval = parseFloat(
  import.meta.env.VITE_REFETCH_INTERVAL_MS || "120000",
); // default: 2 minutes

export const devicesQuery = queryOptions({
  queryKey: ["devices"],
  queryFn: async () => await getDevices(),
  refetchInterval,
  throwOnError: true,
});

export function singleDeviceQuery(name: string) {
  return queryOptions({
    queryKey: ["devices", name],
    queryFn: async () => await getDeviceDetail(name),
    refetchInterval,
    throwOnError: true,
  });
}

export const calibrationsQuery = queryOptions({
  queryKey: ["calibrations"],
  queryFn: async () => await getCalibrations(),
  refetchInterval,
  throwOnError: true,
});

export const currentUserQuery = queryOptions({
  queryKey: ["me"],
  queryFn: async () => await getCurrentUser(),
  throwOnError: true,
});

export function singleDeviceCalibrationQuery(name: string) {
  return queryOptions({
    queryKey: ["calibrations", name],
    queryFn: async () => await getCalibrationsForDevice(name),
    refetchInterval,
    throwOnError: true,
  });
}

export function myJobsQuery(options: { project_id?: string } = {}) {
  const { project_id = "" } = options;
  return queryOptions({
    queryKey: ["me", "jobs", project_id],
    queryFn: async () => await getMyJobs(options),
    refetchInterval,
    throwOnError: true,
  });
}

/**
 * @param options.projectList - the projects whose names the tokens are given
 */
export function myTokensQuery(options: {
  project_id?: string;
  projectList: Project[];
}) {
  const { project_id, projectList } = options;
  return queryOptions({
    queryKey: ["me", "tokens", project_id],
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

export const myProjectsQuery = queryOptions({
  queryKey: ["me", "projects"],
  queryFn: async () => await getMyProjects(),
  refetchInterval,
  throwOnError: true,
});

export const myActiveProjectsQuery = queryOptions({
  queryKey: ["me", "projects", "active"],
  queryFn: async () => await getMyProjects({ is_active: true }),
  refetchInterval,
  throwOnError: true,
});

/**
 * The requests awaiting an admin, which only admins fetch
 *
 * @param options.projectList - the projects the user can see, to name those requested on
 */
export function allUserRequestsQuery(options: {
  status?: UserRequestStatus;
  currentUser: User;
  projectList?: Project[];
  skip?: number;
  limit?: number;
}) {
  const { status, skip = 0, limit, currentUser, projectList = [] } = options;
  const projectIds = projectList.map((v) => v.id).sort();
  const queryKey = ["me", "requests", "approver", status, limit, skip];
  const enabled = currentUser.roles.includes(UserRole.ADMIN);

  return queryOptions({
    queryKey: [...queryKey, projectIds],
    queryFn: async () => {
      const requests = await getMyRequests({
        role: "approver",
        status,
        limit,
        skip,
      });
      return toExtendedUserRequests(requests, projectList);
    },
    refetchInterval,
    enabled,
    throwOnError: true,
  });
}

/** All projects, which only admins fetch */
export function allAdminProjectsQuery(options: {
  is_active?: boolean;
  currentUser: User;
  skip?: number;
  limit?: number;
}) {
  const { is_active, skip = 0, limit, currentUser } = options;
  const queryKey = ["admin", "projects", is_active, limit, skip];
  const enabled = currentUser.roles.includes(UserRole.ADMIN);

  return queryOptions({
    queryKey,
    queryFn: async () => await getAdminProjects({ is_active, limit, skip }),
    refetchInterval,
    enabled,
    throwOnError: true,
  });
}

/** The current user's QPU-time requests on the given projects */
export function myProjectsQpuTimeRequestsQuery(options: {
  status?: UserRequestStatus;
  projects: Project[];
}) {
  const { status, projects } = options;
  const projectIds = projects.map((v) => v.id).sort();
  const types = [UserRequestType.PROJECT_QPU_SECONDS];
  const queryKey = ["me", "requests", "requester", status, types];

  return queryOptions({
    queryKey: [...queryKey, projectIds],
    queryFn: async () => {
      const data = await getMyRequests({ role: "requester", status, types });
      return data.filter((v) => projectIds.includes(v.resource_id));
    },
    refetchInterval,
    throwOnError: true,
  });
}

/** The backend's bookings from now on, by default the next five */
export function upcomingBookingsQuery(options: {
  backend: string;
  user_id?: string;
  max_start_utc?: string;
  skip?: number;
  limit?: number;
  throwOnError?: boolean;
}) {
  const {
    skip = 0,
    backend,
    limit = 5,
    throwOnError = true,
    user_id,
    max_start_utc,
  } = options;
  // min_start_utc is left out as it moves on every refetch
  const queryKey = [
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
      await getFutureBookings(backend, { user_id, max_start_utc, limit, skip }),
    refetchInterval,
    throwOnError,
  });
}

/** @param options.sort - the fields to sort by, descending where prefixed with "-" */
export function bookingsOfBackendQuery(options: {
  backend: string;
  user_id?: string;
  min_start_utc?: string;
  max_start_utc?: string;
  skip?: number;
  limit?: number;
  sort?: string[];
}) {
  const {
    skip = 0,
    backend,
    limit,
    user_id,
    min_start_utc,
    max_start_utc,
    sort,
  } = options;
  const queryKey = [
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
      await getBookingsOfBackend(backend, {
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

export function bookingsConfigQuery(backend: string) {
  return queryOptions({
    queryKey: ["bookings", backend, "config"],
    queryFn: async () => await getBookingsConfig(backend),
    refetchInterval,
    throwOnError: true,
  });
}

export function noticesQuery(
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
) {
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
  } = options;
  const queryKey = [
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
    queryFn: async () => await getNotices(options),
    refetchInterval,
    throwOnError: true,
    placeholderData: keepPreviousData,
  });
}

/** @param options.is_read - filter on read state; omit for either */
export function noticeCountQuery(
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
) {
  const {
    types,
    is_read,
    user_id,
    min_start_utc,
    max_start_utc,
    min_expires_utc,
    max_expires_utc,
    include_dismissed,
  } = options;
  const queryKey = [
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
    queryFn: async () => await getNoticeCount(options),
    refetchInterval,
    throwOnError: true,
  });
}

export function recalibrationInfoQuery(backend: string) {
  return queryOptions({
    queryKey: ["admin", "recalibration", backend, "info"],
    queryFn: async () => await getRecalibrationInfo(backend),
    refetchInterval,
    throwOnError: true,
  });
}

export async function refreshMyTokensQueries(queryClient: QueryClient) {
  await queryClient.invalidateQueries({ queryKey: ["me", "tokens"] });
}

export async function refreshMyProjectsQueries(queryClient: QueryClient) {
  await queryClient.invalidateQueries({ queryKey: ["me", "projects"] });
}

export async function refreshAllAdminQueries(queryClient: QueryClient) {
  await queryClient.invalidateQueries({ queryKey: ["admin"] });
}

export async function refreshBookingsQueries(
  queryClient: QueryClient,
  backend: string,
) {
  await queryClient.invalidateQueries({ queryKey: ["bookings", backend] });
}

export async function refreshAllNotices(queryClient: QueryClient) {
  await queryClient.invalidateQueries({ queryKey: ["admin", "notices"] });
}

export async function refreshAllNoticeCounts(queryClient: QueryClient) {
  await queryClient.invalidateQueries({ queryKey: ["counts", "notices"] });
}

export async function createAppToken(
  payload: AppTokenCreationRequest,
): Promise<AppTokenCreationResponse> {
  const { data } = await client.POST("/me/tokens/", { body: payload });
  return data!;
}

export async function cancelBooking(
  backend: string,
  id: string,
): Promise<GeneralMessage> {
  const { data } = await client.POST("/bookings/{backend}/{booking_id}/cancel", {
    params: { path: { backend, booking_id: id } },
  });
  const resp = data!;
  if (resp.status !== "success") {
    const err = new Error(`${resp.status}: ${resp.detail}`) as ErrorInfo;
    err.statusText = resp.status;
    throw err;
  }

  return resp;
}

export async function updateBooking(
  backend: string,
  id: string,
  payload: NewBookingInfo,
): Promise<Booking> {
  await cancelBooking(backend, id);
  return await createNewBooking(backend, payload);
}

export async function createNewBooking(
  backend: string,
  payload: NewBookingInfo,
): Promise<Booking> {
  const { data } = await client.POST("/bookings/{backend}", {
    params: { path: { backend } },
    body: payload,
  });
  return toClientSideBooking(data! as RawBooking, { backend });
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

export async function requestQpuTimeExtension(
  payload: QpuTimeExtensionPostBody,
): Promise<UserRequest> {
  const { project_id, seconds, reason } = payload;
  const { data } = await client.POST("/me/requests/", {
    body: {
      type: UserRequestType.PROJECT_QPU_SECONDS,
      resource_id: project_id,
      reason,
      metadata: { resource: "project", seconds } as UserRequestMetadata,
    },
  });
  return data! as UserRequest;
}

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

export async function deleteMyToken(id: string): Promise<void> {
  await client.DELETE("/me/tokens/{_id}", { params: { path: { _id: id } } });
}

export async function deleteMyProject(id: string): Promise<void> {
  await client.DELETE("/me/projects/{_id}", { params: { path: { _id: id } } });
}

export async function deleteAdminProject(id: string): Promise<void> {
  await client.DELETE("/admin/projects/{id}", { params: { path: { id } } });
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

export async function createAdminProject(
  payload: AdminCreateProjectBody,
): Promise<AdminProject> {
  const { data } = await client.POST("/admin/projects/", {
    body: { description: "", ...payload },
  });
  return data!;
}

/** @param options.interval - the seconds between recalibrations */
export async function startRecalibration(
  backend: string,
  options: { interval?: number; start_timestamp?: string } = {},
): Promise<GeneralMessage> {
  const { data } = await client.POST(
    "/admin/bcc/recalibration/{backend}/init",
    { params: { path: { backend }, query: options } },
  );
  return data!;
}

export async function getRecalibrationInfo(
  backend: string,
): Promise<RecalibrationInfo> {
  const { data } = await client.GET("/admin/bcc/recalibration/{backend}/info", {
    params: { path: { backend } },
  });
  return data! as RecalibrationInfo;
}

export async function stopRecalibration(
  backend: string,
  options: { ignore_errors?: boolean } = {},
): Promise<GeneralMessage> {
  const { data } = await client.POST(
    "/admin/bcc/recalibration/{backend}/cancel",
    { params: { path: { backend }, query: options } },
  );
  return data!;
}

export async function switchBackendOn(
  backend: string,
): Promise<GeneralMessage> {
  const { data } = await client.POST("/admin/bcc/switch/{backend}/on", {
    params: { path: { backend } },
  });
  return data!;
}

export async function switchBackendOff(
  backend: string,
): Promise<GeneralMessage> {
  const { data } = await client.POST("/admin/bcc/switch/{backend}/off", {
    params: { path: { backend } },
  });
  return data!;
}

export async function getNotices(
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
  const { data } = await client.GET("/admin/notices", {
    params: { query: { ...rest, type: types } },
  });
  return data!.data as Notice[];
}

export async function getNoticeCount(
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
  const { data } = await client.GET("/counts/notices", {
    params: { query: { ...rest, type: types } },
  });
  return data!.count;
}

/** @returns one notice per targeted user, or the one notice for all users */
export async function createNotice(
  payload: NoticePostRequest,
): Promise<Notice[]> {
  const { data } = await client.POST("/admin/notices/", { body: payload });
  return data! as Notice[];
}

export async function deleteNotice(id: string): Promise<void> {
  await client.DELETE("/admin/notices/{notice_id}", {
    params: { path: { notice_id: id } },
  });
}

export async function dismissNotice(id: string): Promise<GeneralMessage> {
  const { data } = await client.POST("/me/notices/{notice_id}/dismiss", {
    params: { path: { notice_id: id } },
  });
  return data!;
}

export async function dismissAllMyNotices(): Promise<GeneralMessage> {
  const { data } = await client.POST("/me/notices/dismiss");
  return data!;
}

async function getDevices(): Promise<Device[]> {
  const { data } = await client.GET("/devices/");
  return data!.data as Device[];
}

async function getDeviceDetail(name: string): Promise<Device> {
  const { data } = await client.GET("/devices/{name}", {
    params: { path: { name } },
  });
  return data! as Device;
}

async function getBookingsConfig(backend: string): Promise<BookingsConfig> {
  const { data } = await client.GET("/bookings/{backend}/config", {
    params: { path: { backend } },
  });
  return data!;
}

async function getCurrentUser(): Promise<User> {
  const { data } = await client.GET("/me/profile");
  return data! as User;
}

async function getCalibrations(): Promise<DeviceCalibration[]> {
  const { data } = await client.GET("/calibrations/");
  return (data!.data as DeviceCalibration[]).map(normalizeCalibrationData);
}

async function getCalibrationsForDevice(
  name: string,
): Promise<DeviceCalibration> {
  const { data } = await client.GET("/calibrations/{name}", {
    params: { path: { name } },
  });
  return normalizeCalibrationData(data! as DeviceCalibration);
}

async function getMyJobs(
  options: { project_id?: string; skip?: number; limit?: number } = {},
): Promise<Job[]> {
  const { data } = await client.GET("/me/jobs/", {
    params: { query: options },
  });
  return data!.data as Job[];
}

async function getMyTokens(
  options: { project_id?: string } = {},
): Promise<AppToken[]> {
  const { project_id } = options;
  const { data } = await client.GET("/me/tokens/", {
    params: { query: { project_id: project_id ? [project_id] : undefined } },
  });
  return data!.data;
}

async function getMyProjects(
  filters: { is_active?: boolean } = {},
): Promise<Project[]> {
  const { data } = await client.GET("/me/projects/", {
    params: { query: filters },
  });
  return data!.data;
}

async function getAdminProjects(options: {
  is_active?: boolean;
  skip?: number;
  limit?: number;
}): Promise<AdminProject[]> {
  const { data } = await client.GET("/admin/projects/", {
    params: { query: options },
  });
  return data!.data;
}

async function getFutureBookings(
  backend: string,
  options: {
    user_id?: string;
    max_start_utc?: string;
    skip?: number;
    limit?: number;
  },
): Promise<Booking[]> {
  const min_start_utc = DateTime.utc().toISO();
  return await getBookingsOfBackend(backend, { ...options, min_start_utc });
}

async function getBookingsOfBackend(
  backend: string,
  options: {
    user_id?: string;
    min_start_utc?: string;
    max_start_utc?: string;
    skip?: number;
    limit?: number;
    sort?: string[];
  },
): Promise<Booking[]> {
  const { data } = await client.GET("/bookings/{backend}", {
    params: { path: { backend }, query: options },
  });
  return data!.data.map((v) => toClientSideBooking(v as RawBooking, { backend }));
}

/** The current user's notices, newest first */
export function myNoticesQuery(
  options: {
    types?: NoticeType[];
    is_read?: boolean;
    skip?: number;
    limit?: number;
  } = {},
) {
  const { types, is_read, skip, limit } = options;
  return queryOptions({
    queryKey: ["me", "notices", types, is_read, skip, limit],
    queryFn: async () => await getMyNotices(options),
    // no polling: the count badge below is what needs to stay fresh, and the list
    // refetches when the panel opens and after any reaction
    throwOnError: true,
    placeholderData: keepPreviousData,
  });
}

/** Which notice types the current user also gets by email */
export function noticePreferencesQuery() {
  return queryOptions({
    queryKey: ["me", "notices", "preferences"],
    queryFn: async () => await getNoticePreferences(),
    throwOnError: true,
  });
}

/**
 * The requests the current user made, or those awaiting their approval
 *
 * @param options.projectList - the projects the user can see, to name those requested on
 */
export function myRequestsQuery(
  options: {
    role?: "requester" | "approver";
    status?: UserRequestStatus;
    types?: UserRequestType[];
    projectList?: Project[];
  } = {},
) {
  const { projectList = [], ...rest } = options;
  const { role = "requester", status, types } = rest;
  const projectIds = projectList.map((v) => v.id).sort();
  return queryOptions({
    queryKey: ["me", "requests", role, status, types, projectIds],
    queryFn: async () => {
      const requests = await getMyRequests({ ...rest, role });
      return toExtendedUserRequests(requests, projectList);
    },
    refetchInterval,
    throwOnError: true,
  });
}

export async function refreshMyNotices(queryClient: QueryClient) {
  await queryClient.invalidateQueries({ queryKey: ["me", "notices"] });
  await refreshAllNoticeCounts(queryClient);
}

export async function refreshMyRequests(queryClient: QueryClient) {
  await queryClient.invalidateQueries({ queryKey: ["me", "requests"] });
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

/** Sets whether the named notice types are also emailed, leaving the rest untouched */
export async function updateNoticePreferences(
  payload: Partial<NoticePreferences>,
): Promise<NoticePreferences> {
  const { data } = await client.PUT("/me/notices/preferences/", {
    body: payload,
  });
  return data! as NoticePreferences;
}

export async function removeProjectMember(args: {
  projectId: string;
  userId: string;
}): Promise<void> {
  await client.DELETE("/me/projects/{_id}/members/{member_id}", {
    params: { path: { _id: args.projectId, member_id: args.userId } },
  });
}

/** User email addresses, for completing the admin project forms */
export function userEmailsQuery(options: { search?: string } = {}) {
  const { search } = options;
  return queryOptions({
    queryKey: ["admin", "user-emails", search],
    queryFn: async () => await getUserEmails(search),
    // a directory of addresses does not go stale in the life of a form, and the list
    // must not blank while the next search is in flight
    staleTime: 5 * 60_000,
    placeholderData: keepPreviousData,
  });
}

async function getUserEmails(search?: string): Promise<string[]> {
  const { data } = await client.GET("/admin/users/emails/", {
    params: { query: { search: search || undefined } },
  });
  return data!;
}

async function getMyNotices(
  options: {
    types?: NoticeType[];
    is_read?: boolean;
    skip?: number;
    limit?: number;
  } = {},
): Promise<Notice[]> {
  const { types, ...rest } = options;
  const { data } = await client.GET("/me/notices/", {
    params: { query: { ...rest, type: types } },
  });
  return data!.data as Notice[];
}

async function getNoticePreferences(): Promise<NoticePreferences> {
  const { data } = await client.GET("/me/notices/preferences/");
  return data! as NoticePreferences;
}

async function getMyRequests(
  options: {
    role?: "requester" | "approver";
    status?: UserRequestStatus;
    types?: UserRequestType[];
    skip?: number;
    limit?: number;
  } = {},
): Promise<UserRequest[]> {
  const { types, status, ...rest } = options;
  const { data } = await client.GET("/me/requests/", {
    params: {
      query: { ...rest, status: status && [status], type: types },
    },
  });
  return data!.data as UserRequest[];
}

function toExtendedUserRequests(
  requests: UserRequest[],
  projectList: Project[],
): ExtendedUserRequest[] {
  const projectMap = Object.fromEntries(projectList.map((v) => [v.id, v]));
  return requests.map((v) => extendUserRequest(v, projectMap[v.resource_id]));
}
