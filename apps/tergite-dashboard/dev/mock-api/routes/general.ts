import { Router, type Request as ExpressRequest } from "express";
import { type ParsedQs } from "qs";
import cors from "cors";
import {
  AppTokenInDb,
  archiveDb,
  BccUserInDb,
  BookingInDb,
  BookingsConfigInDb,
  conformsToFilter,
  createCookieHeader,
  getAuthenticatedUserId,
  getQueryString,
  getUsername,
  hasAnyOfRoles,
  mockDb,
  respond401,
  forwardAsyncErrors,
  randomUUID,
  getUserNoticesFilter,
  getReadStatusUpdate,
} from "../utils";
import {
  AuthProvider,
  Device,
  DeviceCalibration,
  Job,
  AuthProviderResponse,
  Project,
  User,
  AppToken,
  AppTokenCreationResponse,
  PaginatedData,
  UserRequest,
  UserRequestType,
  UserRequestPostBody,
  UserRequestStatus,
  UserRole,
  AdminProject,
  UpdateProjectPutBody,
  AdminCreateProjectBody,
  BccUserProfile,
  NewBCCUserInfo,
  NewBookingInfo,
  RecalibrationInfo,
  RqJobStatus,
  Notice,
  GeneralMessage,
  CountResponse,
  DbRecord,
  NoticePostRequest,
  NoticePreferences,
  NoticeRefType,
  NoticeType,
  NoticeSeverity,
} from "../types";
import { DateTime } from "luxon";

const currentDateString = process.env.CURRENT_DATE;
const apiBaseUrl = process.env.VITE_API_BASE_URL;
const router = Router();
const _apiStartTimestamp = DateTime.now();
const _initialRecalibrationInfo: RecalibrationInfo = {
  interval: 86_400,
  current_job_id: "current_job_id",
  current_job_status: RqJobStatus.FINISHED,
  current_job_started_at: _apiStartTimestamp.toISO(),

  previous_job_id: "previous_job_id",
  previous_job_status: RqJobStatus.FINISHED,
  previous_job_started_at: _apiStartTimestamp.minus({ days: 1 }).toISO(),
  previous_job_ended_at: _apiStartTimestamp.minus({ hours: 22 }).toISO(),

  next_job_id: "next_job_id",
  next_job_status: RqJobStatus.SCHEDULED,
};
const recalibrationInfoDb: { [key: string]: RecalibrationInfo } = {};

router.use(
  cors({
    origin: true,
    methods: ["GET", "PUT", "POST", "DELETE", "PATCH", "HEAD"],
    credentials: true,
  }),
);

router.options("*", (req, res, next) => {
  next();
});

router.get(
  "/me/profile",
  forwardAsyncErrors(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const data = mockDb.getOne<User>("users", (v) => v.id === currentUserId);

    res.json(data);
  }),
);

router.get(
  "/me/projects/",
  forwardAsyncErrors(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { is_active } = req.query as { [k: string]: string };
    const filters =
      is_active === undefined ? {} : { is_active: is_active === "true" };

    const data = mockDb.getMany<Project>(
      "projects",
      (v) => v.user_ids.includes(currentUserId) && conformsToFilter(v, filters),
    );

    res.json({ skip: 0, limit: null, data } as PaginatedData<Project[]>);
  }),
);

router.delete(
  "/me/projects/:id",
  forwardAsyncErrors(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { params } = req;
    const project = mockDb.getOne<Project>("projects", (v) =>
      conformsToFilter(v, { admin_id: currentUserId, id: params.id }),
    );
    if (project === undefined) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    if (project.is_personal) {
      // recreated on next login with a fresh allowance, so the owner may not do it;
      // a superuser can, through /admin/projects
      res
        .status(403)
        .json({ detail: "you cannot delete your own personal project" });
      return;
    }

    mockDb.del("projects", project.id);
    // Archive this project
    archiveDb.create<Project>("projects", {
      ...project,
      updated_at: new Date().toISOString(),
    });

    // no content
    res.status(204).send();
  }),
);

router.get(
  "/me/jobs/",
  forwardAsyncErrors(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { project_id } = req.query as { [k: string]: string };
    const data = mockDb
      .getMany<Job>("jobs", (v) =>
        conformsToFilter(v, { user_id: currentUserId, project_id }),
      )
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));

    res.json({ skip: 0, limit: null, data } as PaginatedData<Job[]>);
  }),
);

router.post(
  "/me/tokens/",
  forwardAsyncErrors(async (req, res) => {
    const user_id = await getAuthenticatedUserId(req.cookies);
    if (!user_id) {
      return respond401(res);
    }

    const payload = { ...req.body, user_id };
    const project = mockDb.getOne<Project>(
      "projects",
      (v) =>
        v.id === (payload as AppTokenInDb).project_id &&
        v.user_ids.includes(user_id),
    );
    if (!project) {
      return respond401(res);
    }

    const access_token = randomUUID();
    payload["access_token"] = access_token;

    mockDb.create<AppTokenInDb>("tokens", payload);
    res.status(201);
    res.json({
      access_token,
      token_type: "bearer",
    } as AppTokenCreationResponse);
  }),
);

router.get(
  "/me/tokens/",
  forwardAsyncErrors(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { project_id } = req.query as { [k: string]: string };
    const data = mockDb
      .getMany<AppTokenInDb>("tokens", (v) =>
        conformsToFilter(v, { user_id: currentUserId, project_id }),
      )
      .map(toAppToken);

    res.json({ skip: 0, limit: null, data } as PaginatedData<AppToken[]>);
  }),
);

router.delete(
  "/me/tokens/:id",
  forwardAsyncErrors(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { params } = req;
    const token = mockDb.getOne<AppTokenInDb>("tokens", (v) =>
      conformsToFilter(v, { user_id: currentUserId, id: params.id }),
    );
    if (token === undefined) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    mockDb.del("tokens", token.id);

    // no content
    res.status(204).send();
  }),
);

router.put(
  "/me/tokens/:id",
  forwardAsyncErrors(async (req, res) => {
    const user_id = await getAuthenticatedUserId(req.cookies);
    if (!user_id) {
      return respond401(res);
    }

    const { body, params } = req;
    const filterFn = (v: AppTokenInDb) =>
      conformsToFilter(v, { user_id, id: params.id });
    const oldToken = mockDb.getOne<AppTokenInDb>("tokens", filterFn);
    if (!oldToken) {
      res.status(404).json({ detail: `Not Found` });
      return;
    }

    const lifespan_seconds = DateTime.fromISO(body.expires_at).diff(
      DateTime.fromISO(oldToken.created_at),
      "seconds",
    ).seconds;

    const token = mockDb.update<AppTokenInDb>("tokens", filterFn, {
      lifespan_seconds,
    });

    res.json(token && toAppToken(token));
  }),
);

router.get(
  "/devices/",
  forwardAsyncErrors(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const data = mockDb.getMany<Device>("devices");

    res.json({ skip: 0, limit: null, data } as PaginatedData<Device[]>);
  }),
);

router.get(
  "/devices/:name",
  forwardAsyncErrors(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { params } = req;
    const data = mockDb.getOne<Device>(
      "devices",
      (v) => v.name === params.name,
    );

    data
      ? res.json(data)
      : res.status(404).json({ detail: `device '${params.name}' not found` });
  }),
);

router.get(
  "/calibrations/",
  forwardAsyncErrors(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const data = mockDb.getMany<DeviceCalibration>("calibrations");
    res.json({ skip: 0, limit: null, data } as PaginatedData<
      DeviceCalibration[]
    >);
  }),
);

router.get(
  "/calibrations/:name",
  forwardAsyncErrors(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { params } = req;
    const data = mockDb.getOne<DeviceCalibration>(
      "calibrations",
      (v) => v.name === params.name,
    );

    data
      ? res.json(data)
      : res
          .status(404)
          .json({ detail: `calibrations for  '${params.name}' not found` });
  }),
);

router.get(
  "/auth/providers/",
  forwardAsyncErrors(async (req, res) => {
    const { email_domain } = req.query;
    // FIXME: This should return multiple ways in case the same email domain can login in many ways
    const filteredData = mockDb.getMany<AuthProvider>(
      "auth_providers",
      (v) => v.email_domain === email_domain,
    );

    if (filteredData.length === 0) {
      res.status(404).json({ detail: `not found` });
      return;
    }

    const data = filteredData.map((item) => ({
      url: `${apiBaseUrl}/auth/${item.name}/auto-authorize`,
      name: item.name,
    }));

    res.json({ skip: 0, limit: null, data } as PaginatedData<
      AuthProviderResponse[]
    >);
  }),
);

router.get(
  "/auth/:provider/auto-authorize",
  forwardAsyncErrors(async (req, res) => {
    const queryString = getQueryString(req.query);
    return res.redirect(`${apiBaseUrl}/oauth/callback${queryString}`);
  }),
);

router.post(
  "/auth/logout",
  forwardAsyncErrors(async (req, res) => {
    // FIXME: Add a next query param
    const userId = await getAuthenticatedUserId(req.cookies);
    const user = mockDb.getOne<User>("users", (v) => v.id === userId);

    if (user) {
      const staleCookieHeader = await createCookieHeader(user, -7_200_000);
      res.set("Set-Cookie", staleCookieHeader);
    }

    res.json({ message: "logged out" });
  }),
);

router.get(
  "/admin/projects/",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const {
      is_active: isActiveStr,
      skip: skipAsString,
      limit: limitAsString,
    } = req.query;
    const skip = skipAsString ? parseInt(skipAsString as string) : undefined;
    const limit = limitAsString ? parseInt(limitAsString as string) : undefined;
    const is_active = isActiveStr ? Boolean(isActiveStr as string) : undefined;

    const projects = mockDb.getMany<Project>(
      "projects",
      (v) => is_active === undefined || v.is_active === is_active,
      skip,
      limit,
    );

    const users = mockDb.getMany<User>("users");
    const userIdEmailMap = Object.fromEntries(
      users.map((v) => [v.id, v.email]),
    );

    const data: AdminProject[] = projects.map((v) => ({
      ...v,
      user_emails: v.user_ids.map((item) => userIdEmailMap[item]),
      admin_email: userIdEmailMap[v.admin_id],
    }));

    res.json({ skip, limit, data });
  }),
);

router.post(
  "/admin/projects/",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const body = req.body as AdminCreateProjectBody;
    const { user_emails = [], admin_email, ...restOfBody } = body;
    const allEmails = [...new Set(user_emails.concat([admin_email]))].filter(
      (v) => v != undefined,
    );
    const userEmailIdMap = getUserEmailIdMap(allEmails as string[]);

    const timestamp = new Date().toISOString();
    const newProject = {
      ...restOfBody,
      updated_at: timestamp,
      created_at: timestamp,
      id: randomUUID(),
    } as Partial<Project>;

    newProject.user_ids = allEmails.map((v) => userEmailIdMap[v]);
    newProject.admin_id = userEmailIdMap[admin_email];

    const project = mockDb.create<Project>("projects", newProject);

    res.json(project);
  }),
);

router.put(
  "/admin/projects/:id",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const projectId = req.params.id;
    const body = req.body as UpdateProjectPutBody;
    const { user_emails = [undefined], admin_email, ...restOfBody } = body;
    const allEmails = [...new Set(user_emails.concat([admin_email]))].filter(
      (v) => v != undefined,
    );
    const userEmailIdMap = getUserEmailIdMap(allEmails as string[]);

    const newUpdate = {
      ...restOfBody,
      updated_at: new Date().toISOString(),
    } as Partial<Project>;
    if (user_emails) {
      newUpdate.user_ids = allEmails.map((v) => userEmailIdMap[v]);
    }

    if (admin_email) {
      newUpdate.admin_id = userEmailIdMap[admin_email];
    }

    const project = mockDb.update<Project>(
      "projects",
      (v) => v.id === projectId,
      newUpdate,
    );
    if (!project) {
      res.status(404).json({ detail: `Not Found` });
      return;
    }

    res.json(project);
  }),
);

router.delete(
  "/admin/projects/:id",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { params } = req;
    const project = mockDb.getOne<Project>(
      "projects",
      (v) => v.id == params.id,
    );
    if (!project) {
      res.status(404).json({ detail: `Not Found` });
      return;
    }

    mockDb.del("projects", project.id);
    // Archive this project
    archiveDb.create<Project>("projects", {
      ...project,
      updated_at: new Date().toISOString(),
    });

    // no content
    res.status(204).send();
  }),
);

router.get(
  "/admin/bcc/users/:backend",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { skip: skipAsString, limit: limitAsString } = req.query;
    const { backend } = req.params;
    const skip = skipAsString ? parseInt(skipAsString as string) : undefined;
    const limit = limitAsString ? parseInt(limitAsString as string) : undefined;

    const bccUsers = mockDb.getMany<BccUserInDb>(
      "bcc_users",
      (v) => v.backend === backend,
      skip,
      limit,
    );

    const data: BccUserProfile[] = bccUsers.map(
      ({ password: _p, backend: _b, ...rest }) => ({
        ...rest,
      }),
    );
    res.json({ skip, limit, data });
  }),
);

router.post(
  "/admin/bcc/users/:backend",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const body = req.body as NewBCCUserInfo;
    const { backend } = req.params;
    const bccUsersWithSameEmail = mockDb.getMany<BccUserInDb>(
      "bcc_users",
      (v) => v.email === body.email && v.backend === backend,
    );

    if (bccUsersWithSameEmail.length > 0) {
      res.status(409).json({ detail: `Conflict` });
      return;
    }

    const bccUser = mockDb.create<BccUserInDb>("bcc_users", {
      ...body,
      backend,
    });

    res.json(bccUser);
  }),
);

router.delete(
  "/admin/bcc/users/:backend/:id",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { id: bccUserId, backend } = req.params;

    const bccUser = mockDb.getOne<BccUserInDb>("bcc_users", (v) =>
      conformsToFilter(v, { backend, id: bccUserId }),
    );
    if (!bccUser) {
      res.status(404).json({ detail: `NotFound` });
      return;
    }

    mockDb.del("bcc_users", bccUserId);

    res.json({ status: "success", detail: "User deleted" });
  }),
);

router.post(
  "/bookings/:backend",
  forwardAsyncErrors(async (req, res) => {
    const user_id = await getAuthenticatedUserId(req.cookies);
    if (!user_id) {
      return respond401(res);
    }

    const body = req.body as NewBookingInfo;
    const { backend } = req.params;

    const user = mockDb.getOne<User>("users", (v) => v.id === user_id);
    if (!user) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const bookingStartUtc = DateTime.fromISO(body.start_utc);
    const bookingConfig = mockDb.getOne<BookingsConfigInDb>(
      "bookings_configs",
      ({ id }) => id === backend,
    );
    const bookingsThatDay = mockDb.getMany<BookingInDb>(
      "bookings",
      (v) =>
        v.user_id === user_id &&
        v.backend === backend &&
        DateTime.fromISO(v.start_utc).hasSame(bookingStartUtc, "day"),
    );

    if (
      bookingConfig?.max_slots_per_day != undefined &&
      bookingsThatDay.length >= bookingConfig.max_slots_per_day
    ) {
      res.status(400).json({
        detail: `you have exceeded the maximum ${bookingConfig?.max_slots_per_day} bookings per day`,
      });
      return;
    }

    const result = mockDb.create<BookingInDb>("bookings", {
      ...body,
      username: user.email.split("@")[0],
      user_id,
      backend,
    });

    const { backend: _, ...booking } = result;
    res.json(booking);
  }),
);

router.post(
  "/bookings/:backend/:id/cancel",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const isUserAdmin = hasAnyOfRoles(userId, [UserRole.ADMIN]);
    const { id: bookingId, backend } = req.params;

    const booking = mockDb.getOne<BookingInDb>(
      "bookings",
      (v) =>
        conformsToFilter(v, { backend, id: bookingId }) &&
        (v.user_id == userId || isUserAdmin),
    );
    if (!booking) {
      res
        .status(404)
        .json({ detail: `the booking of id ${bookingId} was not found` });
      return;
    }

    const startTimestamp = DateTime.fromISO(booking.start_utc);
    const endTimestamp = DateTime.fromISO(booking.end_utc);
    // we sometimes mock now especially during tests so we need
    // to ensure this does not fail at such times.
    const now = currentDateString
      ? DateTime.fromISO(currentDateString)
      : DateTime.now();

    if (startTimestamp <= now && endTimestamp >= now) {
      res
        .status(400)
        .json({ detail: `the booking of id ${bookingId} is already active` });
      return;
    } else if (endTimestamp < now) {
      res
        .status(400)
        .json({ detail: `the booking of id ${bookingId} is already complete` });
      return;
    }

    mockDb.del("bookings", bookingId);
    res.json({
      status: "success",
      detail: `Booking of id ${bookingId} cancelled`,
    });
  }),
);

router.get(
  "/bookings/:backend/config",
  forwardAsyncErrors(async (req, res) => {
    // TODO: Add filtering by date or something, also in backend and MSS
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const { backend } = req.params;

    const bookingsConfigsInDb = mockDb.getOne<BookingsConfigInDb>(
      "bookings_configs",
      (v) => v.id === backend,
    );
    if (!bookingsConfigsInDb) {
      res.status(404).json({ detail: `NotFound` });
      return;
    }

    const { id: _, ...data } = bookingsConfigsInDb;
    res.json(data);
  }),
);

router.get(
  "/bookings/:backend",
  forwardAsyncErrors(async (req, res) => {
    const requesterId = await getAuthenticatedUserId(req.cookies);
    if (!requesterId) {
      return respond401(res);
    }

    const {
      skip: skipAsString,
      limit: limitAsString,
      min_start_utc: minStartUtcAsString,
      max_start_utc: maxStartUtcAsString,
      user_id: userId,
      sort: sortQueryParam,
    } = req.query;
    const { backend } = req.params;
    const skip = skipAsString ? parseInt(skipAsString as string) : undefined;
    const limit = limitAsString ? parseInt(limitAsString as string) : undefined;
    const minStartUtc =
      minStartUtcAsString && DateTime.fromISO(`${minStartUtcAsString}`);
    const maxStartUtc =
      maxStartUtcAsString && DateTime.fromISO(`${maxStartUtcAsString}`);
    const sort =
      typeof sortQueryParam === "string"
        ? [sortQueryParam]
        : (sortQueryParam as string[] | undefined);

    const data = mockDb.getMany<BookingInDb>(
      "bookings",
      (v) =>
        v.backend === backend &&
        (minStartUtc ? DateTime.fromISO(v.start_utc) >= minStartUtc : true) &&
        (maxStartUtc ? DateTime.fromISO(v.start_utc) <= maxStartUtc : true) &&
        (userId ? v.user_id == userId : true),
      skip,
      limit,
      sort,
    );

    res.json({ skip, limit, data });
  }),
);

router.post(
  "/admin/bcc/recalibration/:backend/init",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const {
      interval: intervalAsString,
      start_timestamp: startTimestampAsString,
    } = req.query;
    const { backend } = req.params;
    const recalibrationInfo = recalibrationInfoDb[backend] || {
      ..._initialRecalibrationInfo,
    };

    if (intervalAsString) {
      recalibrationInfo.interval = parseFloat(intervalAsString as string);
    }

    if (startTimestampAsString) {
      recalibrationInfo.next_job_enqueued_at = startTimestampAsString as string;
    }

    recalibrationInfoDb[backend] = recalibrationInfo;

    res.json({ status: "success" });
  }),
);

router.get(
  "/admin/bcc/recalibration/:backend/info",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { backend } = req.params;

    // eslint-disable-next-line no-prototype-builtins
    if (!recalibrationInfoDb.hasOwnProperty(backend)) {
      recalibrationInfoDb[backend] = { ..._initialRecalibrationInfo };
    }

    res.json(recalibrationInfoDb[backend]);
  }),
);

router.post(
  "/admin/bcc/recalibration/:backend/cancel",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { ignore_errors: _ignoreErrorsAsString } = req.query;
    const { backend } = req.params;

    delete recalibrationInfoDb[backend];

    res.json({ status: "success" });
  }),
);

router.post(
  "/admin/bcc/switch/:backend/on",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { backend } = req.params;
    const device = mockDb.getOne<Device>("devices", (v) => v.name === backend);
    if (!device) {
      res.status(404).json({ detail: `device '${backend}' not found` });
      return;
    }

    mockDb.update<Device>("devices", (v) => v.name === backend, {
      is_online: true,
    });

    res.json({ status: "success" } as GeneralMessage);
  }),
);

router.post(
  "/admin/bcc/switch/:backend/off",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { backend } = req.params;
    const device = mockDb.getOne<Device>("devices", (v) => v.name === backend);
    if (!device) {
      res.status(404).json({ detail: `device '${backend}' not found` });
      return;
    }

    mockDb.update<Device>("devices", (v) => v.name === backend, {
      is_online: false,
      last_online: new Date().toISOString(),
    });

    res.json({ status: "success" } as GeneralMessage);
  }),
);

router.post(
  "/admin/notices/",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { message, severity, starts_at, expires_at, target_user_emails } =
      req.body as NoticePostRequest;
    const fields = {
      title: message,
      body: message,
      severity,
      created_by: userId,
      ref_type: null,
      ref_id: null,
      read_at: null,
      dismissed_by: [],
      starts_at,
      expires_at,
    };

    // one notice per targeted user, like the API, or one for everyone
    const data = target_user_emails
      ? mockDb
          .getMany<User>("users", (v) => target_user_emails.includes(v.email))
          .map((user) =>
            mockDb.create<Notice>("notices", {
              ...fields,
              type: NoticeType.CUSTOM,
              user_id: user.id,
            }),
          )
      : [
          mockDb.create<Notice>("notices", {
            ...fields,
            type: NoticeType.CUSTOM_BROADCAST,
            user_id: null,
          }),
        ];

    res.status(200);
    res.json(data);
  }),
);

router.get(
  "/admin/notices",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const {
      skip: skipAsString,
      limit: limitAsString,
      sort: sortQuery,
      user_id,
    } = req.query;
    const skip = skipAsString ? parseInt(skipAsString as string, 10) : 0;
    const limit = limitAsString
      ? parseInt(limitAsString as string, 10)
      : undefined;
    const sort = sortQuery
      ? ([] as string[]).concat(sortQuery as string | string[])
      : ["starts_at"];

    const filterFunc = getUserNoticesFilter(req, user_id as string | undefined);
    const data = mockDb.getMany<Notice>(
      "notices",
      filterFunc,
      skip,
      limit,
      sort,
    );

    res.status(200);
    res.json({ skip, limit: limit ?? null, data } as PaginatedData<Notice[]>);
  }),
);

router.delete(
  "/admin/notices/:id",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { id } = req.params;
    const notice = mockDb.getOne<Notice>("notices", (v) => v.id === id);
    if (!notice) {
      res.status(404).json({ detail: `notice of ID '${id}' not found` });
      return;
    }

    mockDb.del("notices", id);
    res.status(200);
    res.json(notice);
  }),
);

router.get(
  "/counts/notices",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const { user_id } = req.query;

    const isAdmin = hasAnyOfRoles(userId, [UserRole.ADMIN]);
    // ensure that ordinary users only query their own notices
    const noticesUserId = isAdmin ? (user_id as string | undefined) : userId;

    const filterFunc = getUserNoticesFilter(req, noticesUserId);
    const data = mockDb.getMany<Notice>("notices", filterFunc);

    res.status(200);
    res.json({ count: data.length } as CountResponse);
  }),
);

router.get(
  "/me/notices/",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const { skip = "0", limit } = req.query as ParsedQs & {
      skip?: string;
      limit?: string;
    };
    // the API includes the read notices here, unless is_read says otherwise
    req.query.include_dismissed = "true";
    const data = mockDb.getMany<Notice>(
      "notices",
      getUserNoticesFilter(req, userId),
      parseInt(skip),
      limit ? parseInt(limit) : undefined,
      ["-created_at"],
    );

    res.json({
      skip: parseInt(skip),
      limit: limit ? parseInt(limit) : null,
      data,
    } as PaginatedData<Notice[]>);
  }),
);

router.post(
  "/me/notices/dismiss",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const count = setReadStatusOfMyNotices(req, userId, true);
    res.json({
      status: "success",
      detail: `${count} notices updated`,
    } as GeneralMessage);
  }),
);

router.post(
  "/me/notices/unread",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const count = setReadStatusOfMyNotices(req, userId, false);
    res.json({
      status: "success",
      detail: `${count} notices updated`,
    } as GeneralMessage);
  }),
);

router.post(
  "/me/notices/:id/dismiss",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    if (!setReadStatusOfMyNotice(req.params.id, userId, true)) {
      res
        .status(404)
        .json({ detail: `notice of ID '${req.params.id}' not found` });
      return;
    }
    res.json({ status: "success" } as GeneralMessage);
  }),
);

router.post(
  "/me/notices/:id/unread",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    if (!setReadStatusOfMyNotice(req.params.id, userId, false)) {
      res
        .status(404)
        .json({ detail: `notice of ID '${req.params.id}' not found` });
      return;
    }
    res.json({ status: "success" } as GeneralMessage);
  }),
);

router.get(
  "/me/notices/preferences/",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    res.json(getEffectivePrefs(userId));
  }),
);

router.put(
  "/me/notices/preferences/",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const wanted = req.body as Partial<NoticePreferences>;
    const knownTypes = Object.values(NoticeType) as string[];
    if (Object.keys(wanted).some((v) => !knownTypes.includes(v))) {
      res.status(422).json({ detail: "unknown notice type" });
      return;
    }

    const current = { ...getEffectivePrefs(userId), ...wanted };
    savePrefs(userId, current);
    res.json(current);
  }),
);

router.post(
  "/me/requests/",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const requester = mockDb.getOne<User>("users", (v) => v.id === userId)!;
    const body = req.body as UserRequestPostBody;
    const metadata = {
      resource: NoticeRefType.PROJECT,
      ...(body.metadata ?? {}),
    };
    if (body.type === UserRequestType.PROJECT_QPU_SECONDS && !metadata.seconds) {
      res.status(422).json({ detail: "seconds are required" });
      return;
    }

    const project = mockDb.getOne<Project>(
      "projects",
      (v) => v.id === body.resource_id,
    );
    if (!hasRequestAccess(body.type, userId, project)) {
      res.status(403).json({
        detail: `operation not permitted on resource ${body.resource_id}`,
      });
      return;
    }

    const isForProject = body.type === UserRequestType.PROJECT_ACCESS;
    // personal projects answer 404 to access requests, like missing ones
    if (isForProject && (!project || project.is_personal)) {
      res.status(404).json({ detail: `project ${body.resource_id} not found` });
      return;
    }

    const targetUserIds = isForProject
      ? [project!.admin_id]
      : mockDb
          .getMany<User>("users", (v) => v.roles.includes(UserRole.ADMIN))
          .map((v) => v.id);
    const created = mockDb.create<UserRequest>("user_requests", {
      type: body.type,
      resource_id: body.resource_id,
      reason: body.reason,
      metadata,
      requester_id: userId,
      requester_name: getUsername(requester),
      target_user_ids: targetUserIds,
      target: isForProject ? "project" : "system",
      status: UserRequestStatus.PENDING,
      approver_id: null,
      approver_name: null,
      rejection_reason: null,
    });

    for (const targetUserId of targetUserIds) {
      createSystemNotice({
        user_id: targetUserId,
        type: REQUESTED_NOTICE_TYPES[body.type],
        title: `${describeRequest(created)}?`,
        body: `${getUsername(requester)} is asking: ${body.reason}`,
        severity: NoticeSeverity.INFO,
        ref_type: created.metadata.resource,
        ref_id: created.id,
      });
    }

    res.status(201).json(created);
  }),
);

router.get(
  "/me/requests/",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const {
      role = "approver",
      status,
      type,
      skip = "0",
      limit,
    } = req.query as ParsedQs & {
      role?: string;
      status?: string | string[];
      type?: string | string[];
      skip?: string;
      limit?: string;
    };
    const statuses = status ? ([] as string[]).concat(status) : [];
    const types = type ? ([] as string[]).concat(type) : [];

    const data = mockDb.getMany<UserRequest>(
      "user_requests",
      (v) =>
        (statuses.length === 0 || statuses.includes(v.status)) &&
        (types.length === 0 || types.includes(v.type)) &&
        (role === "approver"
          ? v.target_user_ids.includes(userId)
          : v.requester_id === userId),
      parseInt(skip),
      limit ? parseInt(limit) : undefined,
      ["-created_at"],
    );

    res.json({
      skip: parseInt(skip),
      limit: limit ? parseInt(limit) : null,
      data,
    } as PaginatedData<UserRequest[]>);
  }),
);

router.put(
  "/me/requests/:id",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const actor = mockDb.getOne<User>("users", (v) => v.id === userId)!;
    // only the users a pending request is directed to can decide it
    const request = mockDb.getOne<UserRequest>(
      "user_requests",
      (v) =>
        v.id === req.params.id &&
        v.target_user_ids.includes(userId) &&
        v.status === UserRequestStatus.PENDING,
    );
    if (!request) {
      res.status(404).json({ detail: "no match found" });
      return;
    }

    const body = req.body as Pick<UserRequest, "status" | "rejection_reason">;
    if (body.status === UserRequestStatus.APPROVED) {
      applyApproval(request);
    }

    const updated = mockDb.update<UserRequest>(
      "user_requests",
      (v) => v.id === request.id,
      { ...body, approver_id: userId, approver_name: getUsername(actor) },
    );

    if (body.status !== undefined && body.status !== UserRequestStatus.PENDING) {
      const isApproved = body.status === UserRequestStatus.APPROVED;
      // the prompts to decide it are no longer of any consequence
      for (const notice of mockDb.getMany<Notice>(
        "notices",
        (v) => v.ref_id === request.id && !v.read_at,
      )) {
        mockDb.update<Notice>(
          "notices",
          (v) => v.id === notice.id,
          getReadStatusUpdate(notice, notice.user_id!, true),
        );
      }
      createSystemNotice({
        user_id: request.requester_id,
        type: (isApproved ? APPROVED_NOTICE_TYPES : REJECTED_NOTICE_TYPES)[
          request.type
        ],
        title: `${describeRequest(request)}: ${body.status}`,
        body: `${getUsername(actor)} ${isApproved ? "approved" : "declined"} your request. ${body.rejection_reason ?? ""}`,
        severity: isApproved ? NoticeSeverity.INFO : NoticeSeverity.WARNING,
        ref_type: request.metadata.resource,
        ref_id: request.id,
      });
    }

    res.json(updated);
  }),
);

router.delete(
  "/me/projects/:id/members/:memberId",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const actor = mockDb.getOne<User>("users", (v) => v.id === userId);
    const project = mockDb.getOne<Project>(
      "projects",
      (v) => v.id === req.params.id,
    );
    if (!project) {
      res.status(404).json({ detail: "Not Found" });
      return;
    }

    const isAdmin = !!actor?.roles.includes(UserRole.ADMIN);
    if (!actor || !(isAdmin || project.admin_id === userId)) {
      res.status(403).json({ detail: "Forbidden" });
      return;
    }

    if (req.params.memberId === project.admin_id) {
      res.status(400).json({ detail: "the project admin cannot be removed" });
      return;
    }

    const member = mockDb.getOne<User>(
      "users",
      (v) => v.id === req.params.memberId,
    );
    if (!member || !project.user_ids.includes(member.id)) {
      res.status(204).send();
      return;
    }

    mockDb.update<Project>("projects", (v) => v.id === project.id, {
      user_ids: project.user_ids.filter((v) => v !== member.id),
    });

    createSystemNotice({
      user_id: member.id,
      type: NoticeType.PROJECT_MEMBERSHIP_REVOKED,
      title: `You were removed from ${project.name}`,
      body: `${getUsername(actor)} removed you from ${project.name}. Any API tokens you held for it no longer work.`,
      severity: NoticeSeverity.WARNING,
      ref_type: NoticeRefType.PROJECT,
      ref_id: project.id,
    });

    res.status(204).send();
  }),
);

/**
 * The notice types the user also gets by email, defaults filled in for every type
 *
 * @param userId - the id of the user whose preferences are wanted
 */
function getEffectivePrefs(userId: string): NoticePreferences {
  const stored = mockDb.getOne<NoticePrefsInDb>(
    "notice_prefs",
    (v) => v.user_id === userId,
  );
  const prefs = {} as NoticePreferences;
  for (const type of Object.values(NoticeType)) {
    prefs[type] = stored?.prefs?.[type] ?? true;
  }
  return prefs;
}

/**
 * Persists the user's full preference map
 *
 * @param userId - the id of the user whose preferences are saved
 * @param prefs - the full effective preference map
 */
function savePrefs(userId: string, prefs: NoticePreferences) {
  const existing = mockDb.getOne<NoticePrefsInDb>(
    "notice_prefs",
    (v) => v.user_id === userId,
  );
  if (existing) {
    mockDb.update<NoticePrefsInDb>(
      "notice_prefs",
      (v) => v.id === existing.id,
      { prefs },
    );
    return;
  }
  mockDb.create<NoticePrefsInDb>("notice_prefs", { user_id: userId, prefs });
}

/**
 * Creates a notice the system emits on some event, for one user
 *
 * @param fields - the fields that differ between such notices
 */
function createSystemNotice(
  fields: Pick<
    Notice,
    "user_id" | "type" | "title" | "body" | "severity" | "ref_type" | "ref_id"
  >,
) {
  mockDb.create<Notice>("notices", {
    ...fields,
    created_by: null,
    read_at: null,
    dismissed_by: [],
    starts_at: null,
    expires_at: null,
  });
}

/**
 * Marks one notice addressed to the given user read or unread
 *
 * @param noticeId - the id of the notice
 * @param userId - the id of the user
 * @param isRead - whether to mark it read or unread
 * @returns whether the notice was found
 */
function setReadStatusOfMyNotice(
  noticeId: string,
  userId: string,
  isRead: boolean,
): boolean {
  const notice = mockDb.getOne<Notice>(
    "notices",
    (v) => v.id === noticeId && (!v.user_id || v.user_id === userId),
  );
  if (!notice) {
    return false;
  }

  mockDb.update<Notice>(
    "notices",
    (v) => v.id === noticeId,
    getReadStatusUpdate(notice, userId, isRead),
  );
  return true;
}

/**
 * Marks every notice of the given user read or unread
 *
 * @param req - the request, whose query can narrow down the notices
 * @param userId - the id of the user
 * @param isRead - whether to mark them read or unread
 * @returns the number of notices updated
 */
function setReadStatusOfMyNotices(
  req: ExpressRequest,
  userId: string,
  isRead: boolean,
): number {
  req.query.include_dismissed = "true";
  req.query.is_read = `${!isRead}`;
  const notices = mockDb.getMany<Notice>(
    "notices",
    getUserNoticesFilter(req, userId),
  );
  for (const notice of notices) {
    mockDb.update<Notice>(
      "notices",
      (v) => v.id === notice.id,
      getReadStatusUpdate(notice, userId, isRead),
    );
  }
  return notices.length;
}

/**
 * Whether the given user may make a request of the given type, like the API
 *
 * @param type - the type of the request
 * @param userId - the id of the user making the request
 * @param project - the project the request is about, if any
 */
function hasRequestAccess(
  type: UserRequestType,
  userId: string,
  project?: Project,
): boolean {
  switch (type) {
    case UserRequestType.CLOSE_PROJECT:
    case UserRequestType.TRANSFER_PROJECT:
      return project?.admin_id === userId;
    case UserRequestType.PROJECT_QPU_SECONDS:
      return !!project?.user_ids.includes(userId);
    default:
      return true;
  }
}

/**
 * Does what the given request asks for, as the API does on approving it
 *
 * @param request - the request being approved
 */
function applyApproval(request: UserRequest) {
  const { metadata } = request;
  const project = mockDb.getOne<Project>(
    "projects",
    (v) => v.id === request.resource_id,
  );
  const users = mockDb.getMany<User>("users");
  const userIdOf = (email?: string) => users.find((v) => v.email === email)?.id;

  switch (request.type) {
    case UserRequestType.PROJECT_ACCESS:
      mockDb.update<Project>("projects", (v) => v.id === project!.id, {
        user_ids: [...new Set([...project!.user_ids, request.requester_id])],
      });
      break;
    case UserRequestType.PROJECT_QPU_SECONDS:
      mockDb.update<Project>("projects", (v) => v.id === project!.id, {
        qpu_seconds: project!.qpu_seconds + (metadata.seconds ?? 0),
      });
      break;
    case UserRequestType.TRANSFER_PROJECT: {
      const adminId = userIdOf(metadata.admin_email)!;
      mockDb.update<Project>("projects", (v) => v.id === project!.id, {
        admin_id: adminId,
        user_ids: [...new Set([...project!.user_ids, adminId])],
      });
      break;
    }
    case UserRequestType.CLOSE_PROJECT:
      mockDb.del("projects", project!.id);
      archiveDb.create<Project>("projects", { ...project! });
      break;
    case UserRequestType.CREATE_PROJECT: {
      // like the API, users are created for the emails that have none
      const emails = [...(metadata.user_emails ?? []), metadata.admin_email!];
      const userEmailIdMap = getUserEmailIdMap(emails);
      const adminId = userEmailIdMap[metadata.admin_email!];
      const memberIds = (metadata.user_emails ?? []).map(
        (v) => userEmailIdMap[v],
      );
      mockDb.create<Project>("projects", {
        name: metadata.name,
        description: metadata.description ?? "",
        qpu_seconds: metadata.qpu_seconds ?? 0,
        admin_id: adminId,
        user_ids: [...new Set([...memberIds, adminId])],
        is_active: true,
        is_personal: false,
      });
      break;
    }
  }
}

/**
 * Gets the app token as the API shows it, without its user
 *
 * @param token - the app token as stored
 */
function toAppToken({ user_id: _userId, ...token }: AppTokenInDb): AppToken {
  return token;
}

/**
 * Gets the IDs of the users of the given emails, creating the users that do not exist
 *
 * @param emails - the emails of the users
 * @returns the map of email to user ID
 */
function getUserEmailIdMap(emails: string[]): Record<string, string> {
  const userEmailIdMap: Record<string, string> = Object.fromEntries(
    mockDb.getMany<User>("users").map((v) => [v.email, v.id]),
  );

  for (const email of emails) {
    if (!userEmailIdMap[email]) {
      const newUser = mockDb.create<User>("users", {
        email,
        id: randomUUID(),
        roles: [UserRole.USER],
      });
      userEmailIdMap[email] = newUser.id;
    }
  }

  return userEmailIdMap;
}

/**
 * Describes the given request in a few words, for the notices about it
 *
 * @param request - the request to describe
 */
function describeRequest(request: UserRequest): string {
  // like the API, the project is looked up even after it has been closed
  const isOfRequest = (v: Project) => v.id === request.resource_id;
  const project =
    mockDb.getOne<Project>("projects", isOfRequest) ??
    archiveDb.getOne<Project>("projects", isOfRequest);
  const name = project?.name ?? request.metadata.name ?? request.resource_id;
  return `${request.type} for ${name}`;
}

const REQUESTED_NOTICE_TYPES: Record<UserRequestType, NoticeType> = {
  [UserRequestType.PROJECT_ACCESS]: NoticeType.PROJECT_ACCESS_REQUESTED,
  [UserRequestType.PROJECT_QPU_SECONDS]: NoticeType.QPU_SECONDS_REQUESTED,
  [UserRequestType.CREATE_PROJECT]: NoticeType.PROJECT_CREATE_REQUESTED,
  [UserRequestType.CLOSE_PROJECT]: NoticeType.PROJECT_CLOSE_REQUESTED,
  [UserRequestType.TRANSFER_PROJECT]: NoticeType.PROJECT_TRANSFER_REQUESTED,
};

const APPROVED_NOTICE_TYPES: Record<UserRequestType, NoticeType> = {
  [UserRequestType.PROJECT_ACCESS]: NoticeType.PROJECT_ACCESS_APPROVED,
  [UserRequestType.PROJECT_QPU_SECONDS]: NoticeType.QPU_SECONDS_GRANTED,
  [UserRequestType.CREATE_PROJECT]: NoticeType.PROJECT_CREATE_APPROVED,
  [UserRequestType.CLOSE_PROJECT]: NoticeType.PROJECT_CLOSE_APPROVED,
  [UserRequestType.TRANSFER_PROJECT]: NoticeType.PROJECT_TRANSFER_APPROVED,
};

const REJECTED_NOTICE_TYPES: Record<UserRequestType, NoticeType> = {
  [UserRequestType.PROJECT_ACCESS]: NoticeType.PROJECT_ACCESS_REJECTED,
  [UserRequestType.PROJECT_QPU_SECONDS]: NoticeType.QPU_SECONDS_DENIED,
  [UserRequestType.CREATE_PROJECT]: NoticeType.PROJECT_CREATE_REJECTED,
  [UserRequestType.CLOSE_PROJECT]: NoticeType.PROJECT_CLOSE_REJECTED,
  [UserRequestType.TRANSFER_PROJECT]: NoticeType.PROJECT_TRANSFER_REJECTED,
};

interface NoticePrefsInDb extends DbRecord {
  user_id: string;
  prefs: NoticePreferences;
}

router.get(
  "/admin/users/emails/",
  forwardAsyncErrors(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { search, limit = "20" } = req.query as ParsedQs & {
      search?: string;
      limit?: string;
    };
    const emails = mockDb
      .getMany<User>("users", (v) =>
        search ? v.email.toLowerCase().includes(search.toLowerCase()) : true,
      )
      .map((v) => v.email)
      .sort()
      .slice(0, parseInt(limit));

    res.json(emails);
  }),
);

// NOTE: this mutates the database. I am using GET to avoid CORS issues
router.get("/refreshed-db", (req, res) => {
  mockDb.refresh();
  archiveDb.refresh();

  res.json(mockDb);
});

router.get("/", (req, res) => {
  res.json({ message: "hello world" });
});

export default router;
