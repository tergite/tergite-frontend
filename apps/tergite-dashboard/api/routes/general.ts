import { Router } from "express";
import cors from "cors";
import {
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
  use,
  randomUUID,
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
  QpuTimeExtensionUserRequest,
  UserRequest,
  UserRequestType,
  UserRequestStatus,
  UserRole,
  AdminProject,
  UpdateProjectPutBody,
  AdminCreateProjectBody,
  BccUserProfile,
  NewBCCUserInfo,
  NewBookingInfo,
  Booking,
} from "../../types";
import { DateTime } from "luxon";

const apiBaseUrl = process.env.VITE_API_BASE_URL;
const router = Router();

router.use(
  cors({
    origin: true,
    methods: ["GET", "PUT", "POST", "DELETE", "PATCH", "HEAD"],
    credentials: true,
  })
);

router.options("*", (req, res, next) => {
  next();
});

router.get(
  "/me",
  use(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const data = mockDb.getOne<User>("users", (v) => v.id === currentUserId);

    res.json(data);
  })
);

router.get(
  "/me/projects/",
  use(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { is_active } = req.query as { [k: string]: string };
    const filters =
      is_active === undefined ? {} : { is_active: is_active === "true" };

    const data = mockDb.getMany<Project>(
      "projects",
      (v) => v.user_ids.includes(currentUserId) && conformsToFilter(v, filters)
    );

    res.json({ skip: 0, limit: null, data } as PaginatedData<Project[]>);
  })
);

router.delete(
  "/me/projects/:id",
  use(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { params } = req;
    const project = mockDb.getOne<Project>("projects", (v) =>
      conformsToFilter(v, { admin_id: currentUserId, id: params.id })
    );
    if (project === undefined) {
      res.status(403).json({ detail: `Forbidden` });
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
  })
);

router.get(
  "/me/jobs/",
  use(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { project_id } = req.query as { [k: string]: string };
    const data = mockDb
      .getMany<Job>("jobs", (v) =>
        conformsToFilter(v, { user_id: currentUserId, project_id })
      )
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));

    res.json({ skip: 0, limit: null, data } as PaginatedData<Job[]>);
  })
);

router.post(
  "/me/tokens/",
  use(async (req, res) => {
    const user_id = await getAuthenticatedUserId(req.cookies);
    if (!user_id) {
      return respond401(res);
    }

    const payload = { ...req.body, user_id };
    const project = mockDb.getOne<Project>(
      "projects",
      (v) =>
        v.ext_id == (payload as AppToken).project_ext_id &&
        v.user_ids.includes(user_id)
    );
    if (!project) {
      return respond401(res);
    }

    const access_token = randomUUID();
    payload["access_token"] = access_token;

    mockDb.create<AppToken>("tokens", payload);
    res.status(201);
    res.json({
      access_token,
      token_type: "bearer",
    } as AppTokenCreationResponse);
  })
);

router.get(
  "/me/tokens/",
  use(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { project_ext_id } = req.query as { [k: string]: string };
    const data = mockDb.getMany<AppToken>("tokens", (v) =>
      conformsToFilter(v, { user_id: currentUserId, project_ext_id })
    );

    res.json({ skip: 0, limit: null, data } as PaginatedData<AppToken[]>);
  })
);

router.delete(
  "/me/tokens/:id",
  use(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { params } = req;
    const token = mockDb.getOne<AppToken>("tokens", (v) =>
      conformsToFilter(v, { user_id: currentUserId, id: params.id })
    );
    if (token === undefined) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    mockDb.del("tokens", token.id);

    // no content
    res.status(204).send();
  })
);

router.put(
  "/me/tokens/:id",
  use(async (req, res) => {
    const user_id = await getAuthenticatedUserId(req.cookies);
    if (!user_id) {
      return respond401(res);
    }

    const { body, params } = req;
    const filterFn = (v: AppToken) =>
      conformsToFilter(v, { user_id, id: params.id });
    const oldToken = mockDb.getOne<AppToken>("tokens", filterFn);
    if (!oldToken) {
      res.status(404).json({ detail: `Not Found` });
      return;
    }

    const lifespan_seconds = DateTime.fromISO(body.expires_at).diff(
      DateTime.fromISO(oldToken.created_at),
      "seconds"
    ).seconds;

    const token = mockDb.update<AppToken>("tokens", filterFn, {
      lifespan_seconds,
    });

    res.json(token);
  })
);

router.get(
  "/devices/",
  use(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const data = mockDb.getMany<Device>("devices");

    res.json({ skip: 0, limit: null, data } as PaginatedData<Device[]>);
  })
);

router.get(
  "/devices/:name",
  use(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { params } = req;
    const data = mockDb.getOne<Device>(
      "devices",
      (v) => v.name === params.name
    );

    data
      ? res.json(data)
      : res.status(404).json({ detail: `device '${params.name}' not found` });
  })
);

router.get(
  "/calibrations/",
  use(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const data = mockDb.getMany<DeviceCalibration>("calibrations");
    res.json({ skip: 0, limit: null, data } as PaginatedData<
      DeviceCalibration[]
    >);
  })
);

router.get(
  "/calibrations/:name",
  use(async (req, res) => {
    const currentUserId = await getAuthenticatedUserId(req.cookies);
    if (!currentUserId) {
      return respond401(res);
    }

    const { params } = req;
    const data = mockDb.getOne<DeviceCalibration>(
      "calibrations",
      (v) => v.name === params.name
    );

    data
      ? res.json(data)
      : res
          .status(404)
          .json({ detail: `calibrations for  '${params.name}' not found` });
  })
);

router.get(
  "/auth/providers/",
  use(async (req, res) => {
    const { email_domain } = req.query;
    // FIXME: This should return multiple ways in case the same email domain can login in many ways
    const filteredData = mockDb.getMany<AuthProvider>(
      "auth_providers",
      (v) => v.email_domain === email_domain
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
  })
);

router.get(
  "/auth/:provider/auto-authorize",
  use(async (req, res) => {
    const queryString = getQueryString(req.query);
    return res.redirect(`${apiBaseUrl}/oauth/callback${queryString}`);
  })
);

router.post(
  "/auth/logout",
  use(async (req, res) => {
    // FIXME: Add a next query param
    const userId = await getAuthenticatedUserId(req.cookies);
    const user = mockDb.getOne<User>("users", (v) => v.id === userId);

    if (user) {
      const staleCookieHeader = await createCookieHeader(user, -7_200_000);
      res.set("Set-Cookie", staleCookieHeader);
    }

    res.json({ message: "logged out" });
  })
);

router.get(
  "/admin/qpu-time-requests/",
  use(async (req, res) => {
    const user_id = await getAuthenticatedUserId(req.cookies);
    if (!user_id) {
      return respond401(res);
    }

    const { status, project_id: projectIds } = req.query;

    const data = mockDb.getMany<QpuTimeExtensionUserRequest>(
      "user_requests",
      (v) => {
        return (
          (status === undefined || v.status === status) &&
          (projectIds === undefined ||
            projectIds === v.request.project_id ||
            // @ts-ignore
            projectIds.includes(v.request.project_id))
        );
      }
    );
    res.json({ skip: 0, limit: null, data } as PaginatedData<
      QpuTimeExtensionUserRequest[]
    >);
  })
);

router.post(
  "/admin/qpu-time-requests/",
  use(async (req, res) => {
    const requester_id = await getAuthenticatedUserId(req.cookies);
    if (!requester_id) {
      return respond401(res);
    }

    const project = mockDb.getOne<Project>(
      "projects",
      (v) => v.id === req.body.project_id
    );
    const requester = mockDb.getOne<User>(
      "users",
      (v) => v.id === requester_id
    );
    if (!project || !requester) {
      res.status(404).json({ detail: `Not Found` });
      return;
    }

    if (!project.user_ids.includes(requester_id)) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const currentTimestamp = new Date().toISOString();
    const userRequest: QpuTimeExtensionUserRequest = {
      request: { ...req.body, project_name: project.name },
      requester_id,
      requester_name: getUsername(requester),
      updated_at: currentTimestamp,
      created_at: currentTimestamp,
      type: UserRequestType.PROJECT_QPU_SECONDS,
      status: UserRequestStatus.PENDING,
      id: randomUUID(),
    };

    mockDb.create<QpuTimeExtensionUserRequest>("user_requests", userRequest);
    res.status(201);
    res.json(userRequest);
  })
);

router.get(
  "/admin/user-requests/",
  use(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    // Only admins are permitted here
    if (!hasAnyOfRoles(userId, [UserRole.ADMIN])) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const { status, skip: skipAsString, limit: limitAsString } = req.query;
    const skip = skipAsString ? parseInt(skipAsString as string) : undefined;
    const limit = limitAsString ? parseInt(limitAsString as string) : undefined;

    const data = mockDb.getMany<UserRequest>(
      "user_requests",
      (v) => status === undefined || v.status === status,
      skip,
      limit
    );

    res.json({ skip, limit, data } as PaginatedData<UserRequest[]>);
  })
);

router.put(
  "/admin/user-requests/:id",
  use(async (req, res) => {
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const approver = mockDb.getOne<User>("users", (v) => v.id === userId);
    // Only admins are permitted here
    if (!approver || !approver.roles.includes(UserRole.ADMIN)) {
      res.status(403).json({ detail: `Forbidden` });
      return;
    }

    const userReqId = req.params.id;
    const body = req.body as Partial<UserRequest>;

    const newUpdate = { ...body, updated_at: new Date().toISOString() };
    // only update approver details when status is being updated
    if (body.status !== undefined) {
      newUpdate.approver_name = getUsername(approver);
      newUpdate.approver_id = userId;
    }
    const userRequest = mockDb.update<UserRequest>(
      "user_requests",
      (v) => v.id === userReqId,
      newUpdate
    );
    if (!userRequest) {
      res.status(404).json({ detail: `Not Found` });
      return;
    }

    if (body.status === UserRequestStatus.APPROVED) {
      // update qpu seconds if it is a QpuTimeExtensionUserRequest
      if (userRequest.type === UserRequestType.PROJECT_QPU_SECONDS) {
        const record = userRequest as QpuTimeExtensionUserRequest;
        const original = mockDb.getOne<Project>(
          "projects",
          (v) => v.id === record.request.project_id
        );
        if (!original) {
          res.status(404).json({ detail: `Project not found` });
          return;
        }

        const qpu_seconds = original.qpu_seconds + record.request.seconds;
        mockDb.update<Project>(
          "projects",
          (v) => v.id === record.request.project_id,
          { qpu_seconds }
        );
      }

      // TODO: add more branches for other user request types
    }

    res.json(userRequest);
  })
);

router.get(
  "/admin/projects/",
  use(async (req, res) => {
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
      limit
    );

    const users = mockDb.getMany<User>("users");
    const userIdEmailMap = Object.fromEntries(
      users.map((v) => [v.id, v.email])
    );

    const data: AdminProject[] = projects.map((v) => ({
      ...v,
      user_emails: v.user_ids.map((item) => userIdEmailMap[item]),
      admin_email: userIdEmailMap[v.admin_id],
    }));

    res.json({ skip, limit, data });
  })
);

router.post(
  "/admin/projects/",
  use(async (req, res) => {
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
      (v) => v != undefined
    );
    const users = mockDb.getMany<User>("users");
    const userEmailIdMap = Object.fromEntries(
      users.map((v) => [v.email, v.id])
    );

    // Create the users if the emails don't exist
    for (const email of allEmails) {
      if (!userEmailIdMap[email]) {
        const newUser = mockDb.create<User>("users", {
          email,
          id: randomUUID(),
          roles: [UserRole.USER],
        });

        userEmailIdMap[email] = newUser.id;
      }
    }

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
  })
);

router.put(
  "/admin/projects/:id",
  use(async (req, res) => {
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
      (v) => v != undefined
    );
    const users = mockDb.getMany<User>("users");
    const userEmailIdMap = Object.fromEntries(
      users.map((v) => [v.email, v.id])
    );

    // Create the users if the emails don't exist
    for (const email of allEmails) {
      if (!userEmailIdMap[email]) {
        const newUser = mockDb.create<User>("users", {
          email,
          id: randomUUID(),
          roles: [UserRole.USER],
        });

        userEmailIdMap[email] = newUser.id;
      }
    }

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
      newUpdate
    );
    if (!project) {
      res.status(404).json({ detail: `Not Found` });
      return;
    }

    res.json(project);
  })
);

router.delete(
  "/admin/projects/:id",
  use(async (req, res) => {
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
      (v) => v.id == params.id
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
  })
);

router.get(
  "/admin/bcc-users/:backend/",
  use(async (req, res) => {
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
      limit
    );

    const data: BccUserProfile[] = bccUsers.map(
      ({ password: _p, backend: _b, ...rest }) => ({
        ...rest,
      })
    );
    res.json({ skip, limit, data });
  })
);

router.post(
  "/admin/bcc-users/:backend",
  use(async (req, res) => {
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
      (v) => v.email === body.email && v.backend === backend
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
  })
);

router.delete(
  "/admin/bcc-users/:backend/:id",
  use(async (req, res) => {
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
      conformsToFilter(v, { backend, id: bccUserId })
    );
    if (!bccUser) {
      res.status(404).json({ detail: `NotFound` });
      return;
    }

    mockDb.del("bcc_users", bccUserId);

    res.json({ status: "success", detail: "User deleted" });
  })
);

router.post(
  "/bookings/:backend",
  use(async (req, res) => {
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

    const result = mockDb.create<BookingInDb>("bookings", {
      ...body,
      username: user.email.split("@")[0],
      user_id,
      backend,
    });

    const { backend: _, ...booking } = result;
    res.json(booking);
  })
);

router.post(
  "/bookings/:backend/:id/cancel",
  use(async (req, res) => {
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
        (v.user_id == userId || isUserAdmin)
    );
    if (!booking) {
      res
        .status(404)
        .json({ detail: `the booking of id ${bookingId} was not found` });
      return;
    }

    const startTimestamp = DateTime.fromISO(booking.start_utc);
    const endTimestamp = DateTime.fromISO(booking.end_utc);
    const now = DateTime.now();

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
  })
);

router.get(
  "/bookings/:backend/config",
  use(async (req, res) => {
    // TODO: Add filtering by date or something, also in backend and MSS
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const { backend } = req.params;

    const bookingsConfigsInDb = mockDb.getOne<BookingsConfigInDb>(
      "bookings_configs",
      (v) => v.id === backend
    );
    if (!bookingsConfigsInDb) {
      res.status(404).json({ detail: `NotFound` });
      return;
    }

    const { id: _, ...data } = bookingsConfigsInDb;
    res.json(data);
  })
);

router.get(
  "/bookings/:backend",
  use(async (req, res) => {
    // TODO: Add filtering by date or something, also in backend and MSS
    const userId = await getAuthenticatedUserId(req.cookies);
    if (!userId) {
      return respond401(res);
    }

    const {
      skip: skipAsString,
      limit: limitAsString,
      min_start_utc: minStartUtcAsString,
      max_start_utc: maxStartUtcAsString,
    } = req.query;
    const { backend } = req.params;
    const skip = skipAsString ? parseInt(skipAsString as string) : undefined;
    const limit = limitAsString ? parseInt(limitAsString as string) : undefined;
    const minStartUtc =
      minStartUtcAsString && DateTime.fromISO(`${minStartUtcAsString}`);
    const maxStartUtc =
      maxStartUtcAsString && DateTime.fromISO(`${maxStartUtcAsString}`);

    const bookingsInDb = mockDb.getMany<BookingInDb>(
      "bookings",
      (v) =>
        v.backend === backend &&
        (minStartUtc ? DateTime.fromISO(v.start_utc) >= minStartUtc : true) &&
        (maxStartUtc ? DateTime.fromISO(v.start_utc) <= maxStartUtc : true),
      skip,
      limit
    );

    const data: Booking[] = bookingsInDb.map(({ backend: _, ...rest }) => ({
      ...rest,
    }));
    res.json({ skip, limit, data });
  })
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
