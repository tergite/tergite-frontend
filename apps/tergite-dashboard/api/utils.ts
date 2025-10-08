import { jwtVerify, type JWTVerifyResult, SignJWT } from "jose";
import authProviderList from "../cypress/fixtures/auth-providers.json";
import deviceCalibrationList from "../cypress/fixtures/calibrations.json";
import deviceList from "../cypress/fixtures/device-list.json";
import jobList from "../cypress/fixtures/jobs.json";
import projectList from "../cypress/fixtures/projects.json";
import tokenList from "../cypress/fixtures/tokens.json";
import userList from "../cypress/fixtures/users.json";
import bccUsersFixture from "../cypress/fixtures/bcc-users.json";
import bookingsFixture from "../cypress/fixtures/bookings.json";
import bookingsConfigList from "../cypress/fixtures/bookings-configs.json";
import userRequestList from "../cypress/fixtures/user-requests.json";
import { type ParsedQs } from "qs";
import {
  type NextFunction,
  type Response as ExpressResponse,
  type Request as ExpressRequest,
} from "express";
import {
  AppToken,
  AuthProvider,
  Booking,
  BookingsConfig,
  DbRecord,
  Device,
  DeviceCalibration,
  ErrorInfo,
  Job,
  NewBCCUserInfo,
  NewBookingInfo,
  Project,
  User,
  UserRequest,
  UserRole,
} from "../types";
import { v4 as uuidv4 } from "uuid";

const jwtSecret = process.env.JWT_SECRET ?? "no-token-really-noooo";
const authAudience = process.env.AUTH_AUDIENCE ?? "no-auth-audience-noooo";
const cookieName: string = process.env.VITE_COOKIE_NAME ?? "tergiteauth";
const cookieDomain = process.env.VITE_COOKIE_DOMAIN;
const jwtAlgorithm = "HS256";
const firstUser = userList[0];
const firstUserId = firstUser["id"];
const firstUsername = firstUser["email"].split("@")[0];
const firstUserIsAdmin = firstUser["roles"].includes("admin");

const bccUserList = deviceList
  .map(({ name: backend }) =>
    bccUsersFixture.map((v) =>
      toBccUserInDb(v, backend, firstUserId, firstUserIsAdmin)
    )
  )
  .flat(1);
const bookingList = deviceList
  .map(({ name: backend }) =>
    bookingsFixture.map((v) =>
      toBookingInDb(v, backend, firstUserId, firstUsername)
    )
  )
  .flat(1);

/**
 * Generate a valid test JWT for the given user
 * @param user - the user for whom the JWT is generated
 * @param expiry - the unix timestamp in seconds at which this JWT is to exprire
 * @param options - extra options including
 *        - secret: the JWT secret to use
 *        - audience: the JWT audience
 * @returns - the JSON web token
 */
export async function generateJwt(
  user: User,
  expiry: number,
  options: { secret?: string; audience?: string } = {}
): Promise<string> {
  const { secret = jwtSecret, audience = authAudience } = options;
  const payload = { sub: user.id, roles: [...user.roles] };
  const encodedSecret = new TextEncoder().encode(secret);

  const alg = jwtAlgorithm;
  const audienceList = [audience];

  return await new SignJWT(payload)
    .setProtectedHeader({ alg })
    .setIssuedAt()
    .setAudience(audienceList)
    .setExpirationTime(expiry)
    .sign(encodedSecret);
}

/**
 * Verified a given JWT token
 * @param token - the token to be verified
 * @param options - extra options including
 *        - secret: the JWT secret to use
 *        - audience: the JWT audience
 * @returns - the verifiration result including the claims stored  in the payload
 */
export async function verifyJwtToken(
  token: string,
  options: { secret?: string; audience?: string } = {}
): Promise<JWTVerifyResult> {
  const { secret = jwtSecret, audience = authAudience } = options;
  const algorithms = [jwtAlgorithm];
  const encodedSecret = new TextEncoder().encode(secret);

  return await jwtVerify(token, encodedSecret, { audience, algorithms });
}

/**
 * A random integer capped to the given max value
 *
 * @param max - the maximum possible random number
 * @returns - a random integer
 */
function randInt(max: number): number {
  return Math.floor(Math.random() * max);
}

class MockDb {
  cache: { [k: string | ItemType]: DbRecord[] } = {
    projects: [...(projectList as Project[])],
    users: [...(userList as User[])],
    tokens: [...(tokenList as AppToken[])],
    devices: [...(deviceList as Device[])],
    calibrations: [...(deviceCalibrationList as DeviceCalibration[])],
    jobs: [...(jobList as Job[])],
    bookings: [...(bookingList as BookingInDb[])],
    bookings_configs: [...(bookingsConfigList as BookingsConfigInDb[])],
    user_requests: [...(userRequestList as UserRequest[])],
    auth_providers: [...(authProviderList as AuthProvider[])],
    bcc_users: [...(bccUserList as BccUserInDb[])],
  };
  deleted: { [k: string | ItemType]: DeletedIndex } = {
    projects: {},
    users: {},
    tokens: {},
    devices: {},
    calibrations: {},
    jobs: {},
    bookings: {},
    bookings_configs: {},
    user_requests: {},
    auth_providers: {},
    bcc_users: {},
  };

  constructor() {
    this.refresh = this.refresh.bind(this);
    this.del = this.del.bind(this);
    this.getOne = this.getOne.bind(this);
    this.getMany = this.getMany.bind(this);
    this.update = this.update.bind(this);
    this.create = this.create.bind(this);
    this.refresh();
  }

  /**
   * Refreshes the mock database
   */
  refresh() {
    clearObj(this.cache);
    clearObj(this.deleted);
    const now = new Date().toISOString();

    this.cache = {
      projects: [...(projectList as Project[])],
      users: [...(userList as User[])],
      tokens: bulkUpdate(tokenList, { created_at: now }) as AppToken[],
      devices: [...(deviceList as Device[])],
      calibrations: [...(deviceCalibrationList as DeviceCalibration[])],
      jobs: [...(jobList as Job[])],
      bookings: [...(bookingList as BookingInDb[])],
      bookings_configs: [...(bookingsConfigList as BookingsConfigInDb[])],
      user_requests: [...(userRequestList as UserRequest[])],
      auth_providers: [...(authProviderList as AuthProvider[])],
      bcc_users: [...(bccUserList as BccUserInDb[])],
    };
    this.deleted = {
      projects: {},
      users: {},
      tokens: {},
      devices: {},
      calibrations: {},
      jobs: {},
      bookings: {},
      bookings_configs: {},
      user_requests: {},
      auth_providers: {},
      bcc_users: {},
    };
  }

  /**
   * Delete a item of `itemType`
   * @param itemType - the type of the item to delete
   * @param id - the id of item
   */
  del(itemType: ItemType, id: string) {
    this.deleted[itemType][id] = true;
  }

  /**
   * Gets many items of `itemType`, skipping `skip` upto the given `limit`
   *
   * @param itemType - the type of the item to get
   * @param filterFn - filter function to find given value
   * @param skip - the number of matched items to skip
   * @param limit - the maximum number of items to return
   * @returns - the list of all undeleted projects
   */
  getMany<T extends DbRecord>(
    itemType: ItemType,
    filterFn: FilterFunc<T> = () => true,
    skip: number = 0,
    limit: number | undefined = undefined
  ): T[] {
    return (this.cache[itemType] as T[])
      .filter((item) => filterFn(item) && !this.deleted[itemType][item.id])
      .slice(skip, limit);
  }

  /**
   * Retrieves one item of `itemType` of the given id or undefined
   * if it doesnot exist
   *
   * @param itemType - the type of the item to get
   * @param filterFn - filter function to find given value
   * @returns - the item to return
   */
  getOne<T extends DbRecord>(
    itemType: ItemType,
    filterFn: FilterFunc<T>
  ): T | undefined {
    return (this.cache[itemType] as T[]).filter(
      (item) => filterFn(item) && !this.deleted[itemType][item.id]
    )[0];
  }

  /**
   * Creates the item, returning it on completion. It fails if any of the objects with the same values of unique fields already exist
   *
   * @param itemType - the type of the item to create
   * @param payload - the project to create
   * @param unique_fields - the fields that are unique
   * @returns - the created project
   */
  create<T extends DbRecord>(
    itemType: ItemType,
    payload: UnknownObject | T,
    unique_fields: string[] | undefined = undefined
  ): T {
    const filters = unique_fields?.reduce(
      (prev, k) => ({ ...prev, k: payload[k] }),
      {}
    );
    const preExistingItems =
      filters &&
      this.getOne(itemType, (item) => conformsToFilter(item, filters));

    if (preExistingItems) {
      const error = new Error(`${itemType} already exists`) as ErrorInfo;
      error.status = 400;
      throw error;
    }

    const timestamp = new Date().toISOString();
    const newItem = {
      ...payload,
      id: `${randInt(10000000)}`,
      created_at: timestamp,
      updated_at: timestamp,
    } as T;

    this.cache[itemType].push(newItem);
    return newItem;
  }

  /**
   * Updates the item of `itemType`, returning it on completion. It fails if item does not exist
   * @param itemType - the type of the item to
   * @param filterFn - filter function to find given value
   * @param payload - the updates to add
   * @returns - the updated project
   */
  update<T extends DbRecord>(
    itemType: ItemType,
    filterFn: FilterFunc<T>,
    payload: Partial<T>
  ): T {
    const preExistingItem = this.getOne(itemType, filterFn);
    if (!preExistingItem) {
      const error = new Error("Not Found") as ErrorInfo;
      error.status = 404;
      throw error;
    }

    const newItem = { ...preExistingItem, ...payload };
    this.cache[itemType] = (this.cache[itemType] as T[]).map((item) =>
      filterFn(item) ? newItem : item
    );

    return newItem;
  }
}

/**
 * Whether the item conforms to filters or not
 *
 * @param item - the item to check
 * @param filters - the filters to check against
 * @returns - whether the item confirms to filters or not
 */
export function conformsToFilter<T extends DbRecord>(
  item: T,
  filters: Partial<T>
): boolean {
  return Object.entries(filters).reduce(
    (prev, [k, v]) => prev && (v === undefined ? true : item[k] === v),
    true
  );
}

/**
 * An instance of the mock database
 */
export const mockDb = new MockDb();

/**
 * An instance of the mock database where deleted archives go
 */
export const archiveDb = new MockDb();

/**
 * Clears a given object
 * @param obj - the object to clear
 */
function clearObj(obj: { [key: string]: unknown }) {
  for (const member in obj) delete obj[member];
}

/**
 * Creates a Set-Cookie header value for authentication
 *
 * @param user - the user for JWT token generation
 * @param lifeSpan - the life span of the cookie in milliseconds
 * @returns - the value for the Set-Cookie header
 */
export async function createCookieHeader(
  user: User,
  lifeSpan: number = 7_200_000 /* 2 hours in future */
): Promise<string> {
  const expiryTimestamp = new Date().getTime() + lifeSpan;
  const jwtToken = await generateJwt(user, Math.round(expiryTimestamp / 1000));
  const expiry = new Date(expiryTimestamp).toUTCString();

  return `${cookieName}=${jwtToken}; Domain=${cookieDomain}; Secure; HttpOnly; SameSite=Lax; Path=/; Expires=${expiry}`;
}

/**
 * Checks whether the user is authenticated
 *
 * @param cookies - the cookies to authenticate with
 */
export async function getAuthenticatedUserId(
  cookies: Record<string, string>
): Promise<string | undefined> {
  let accessToken: string | undefined;
  try {
    // There was a weird thing happening where the cookie string
    // took the format of '{accessToken} {cookieName}={accessToken} {cookieName}={accessToken}'
    // I am not sure what that was about :) Just another crazy bug to chase all over the code
    const cookieString = cookies[cookieName];
    const cookieParts = cookieString
      .split(",")
      .map((v) => v.replace(`${cookieName}=`, "").trim());
    accessToken = cookieParts[cookieParts.length - 1];

    const { payload } = await verifyJwtToken(accessToken);
    return payload.sub;
  } catch (error) {
    accessToken && console.error(error);
    return undefined;
  }
}

/**
 * Checks if the given user has any of the given roles
 *
 * @param userId - the ID of the user to check
 * @param roles - the roles to check for
 */
export function hasAnyOfRoles(userId: string, roles: UserRole[]): boolean {
  const user = mockDb.getOne<User>("users", (v) => v.id === userId);
  if (!user) {
    return false;
  }

  if (roles.length === 0) {
    return true;
  }

  for (const role of roles) {
    if (user.roles.includes(role)) {
      return true;
    }
  }

  return false;
}

/**
 * A wrapper around the request handler that handles common tasks on request handlers
 *
 * @param reqHandler - the async request handler for express
 * @returns - a wrapped async request handler
 */
export function use(reqHandler: AsyncRequestHandler): AsyncRequestHandler {
  return async (req, res, next) => {
    try {
      await reqHandler(req, res, next);
    } catch (error) {
      next(error);
    }
  };
}

/**
 * Constructs a URL query string from the express request query object
 *
 * @param query - the query object from the express request object
 * @returns - the query string
 */
export function getQueryString(query: ParsedQs) {
  const queryString = Object.entries(query).reduce(
    (prev, [k, v]) => `${prev}&${k}=${v}`,
    ""
  );

  return queryString ? `?${queryString}` : "";
}

/**
 * Respond with 401 unauthorized
 *
 * @param res - the express response object
 */
export function respond401(res: ExpressResponse) {
  res.status(401).json({ detail: "Unauthorized" });
}

/**
 * Converts an error into an HTTP error
 *
 * @param err - the error object
 * @returns - the HttpError version of the given error
 */
export function toHTTPError(err: Error | HttpError): HttpError {
  if (err instanceof ReferenceError) {
    return { ...err, status: 404 };
  }

  if ("status" in err) {
    return err;
  }

  console.error(err);
  return { ...err, status: 500, message: "unexpected server error" };
}

/**
 * Creates a NotFound ErrorInfo object
 *
 * @param message - the message in the not found error; default="not found"
 * @returns - the NotFoundError
 */
export function NotFound(message: string = "not found"): ErrorInfo {
  return {
    message,
    status: 404,
    name: "NotFound",
  };
}

/**
 * Retrieves the username of the user
 *
 * @param user - the user
 * @returns - the username of the user
 */
export function getUsername(user: User): string {
  return user.email.split("@")[0];
}

/**
 * Updates the all the records with the given update
 *
 * @param records - the records to be updated
 * @param update - the update to add to the records
 * @returns - the updated records
 */
export function bulkUpdate<T extends Record<string, unknown>>(
  records: T[],
  update: Partial<T>
): T[] {
  return records.map((v) => ({ ...v, ...update }));
}

type ItemType =
  | "projects"
  | "users"
  | "bcc_users"
  | "tokens"
  | "devices"
  | "calibrations"
  | "jobs"
  | "bookings"
  | "bookings_configs"
  | "user_requests"
  | "auth_providers";

type DeletedIndex = { [k: string]: boolean };
type UnknownObject = { [key: string]: unknown };
type FilterFunc<T> = (item: T) => boolean;
type AsyncRequestHandler = (
  req: ExpressRequest,
  res: ExpressResponse,
  next: NextFunction
) => Promise<void>;
interface HttpError extends ErrorInfo {
  status: number;
}

/**
 * Converts basic booking data into payload sent when creating a booking
 *
 * @param data - the basic booking info using relative time
 */
export function toBookingPayload({
  starts_in,
  duration,
}: BookingInfo): NewBookingInfo {
  const now = new Date().getTime();
  const startTimestamp = new Date(now + starts_in * 1000);
  const endTimestamp = new Date(startTimestamp.getTime() + duration * 1000);

  return {
    start_utc: startTimestamp.toISOString(),
    end_utc: endTimestamp.toISOString(),
  };
}

/**
 * Creates a randmon UUID and returns it
 */
export function randomUUID(): string {
  return uuidv4();
}

/**
 * Converts basic booking info containing duration and start, to booking as saved in database
 *
 * @param record - the basic booking info
 * @param user_id - the identifier of the user who booked
 * @param username - the username of the user who booked
 */
function toBookingInDb(
  record: BookingInfo,
  backend: string,
  user_id: string,
  username: string
): BookingInDb {
  const bookingPayload = toBookingPayload(record);
  return {
    ...bookingPayload,
    backend,
    user_id,
    username,
    total_duration: record.duration,
    id: randomUUID(),
  };
}

/**
 * Converts basic user info into the user record as saved in the database
 *
 * @param record - the basic user information
 * @param backend - the backend name
 * @param id - the identifier of the bcc user
 * @param is_admin - whether the user is admin or not
 * @returns - the user as saved in the database
 */
function toBccUserInDb(
  record: BccUserInfo,
  backend: string,
  id: string,
  is_admin: boolean = false
): BccUserInDb {
  return {
    ...record,
    is_admin,
    backend,
    id,
  };
}

/**
 * Basic relative info for the booking
 */
interface BookingInfo {
  starts_in: number;
  duration: number;
}

/**
 * Basic relative info for the user
 */
interface BccUserInfo {
  name: string;
  email: string;
  password: string;
}

/**
 * The schema of the BCC user as stored in the database
 */
export interface BccUserInDb extends NewBCCUserInfo {
  backend: string;
}

/**
 * The schema for the Booking as saved in the database
 */
export interface BookingInDb extends Booking {
  backend: string;
}

/**
 * Schema for Bookings
 */
export interface BookingsConfigInDb extends BookingsConfig {
  id: string;
}
