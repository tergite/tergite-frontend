import type { UserRequestMetadata } from "../../src/lib/api/types";

// the mock API's own shapes and enums; the API's shapes are the dashboard's, from MSS's schema
export type {
  AdminCreateProjectBody,
  AdminProject,
  AppToken,
  AppTokenCreationResponse,
  AuthProviderResponse,
  Booking,
  BookingsConfig,
  Device,
  DeviceCalibration,
  GeneralMessage,
  Job,
  NewBookingInfo,
  Notice,
  NoticePostRequest,
  NoticePreferences,
  Project,
  RecalibrationInfo,
  UpdateProjectPutBody,
  User,
  UserRequest,
} from "../../src/lib/api/types";
export type { ErrorInfo } from "../../src/lib/api/client";
export type { ExtendedAppToken } from "../../src/lib/api/tokens";
export type { AnyFlatRecord } from "../../src/lib/user-requests";

export interface DbRecord extends Record<
  string,
  | string
  | number
  | boolean
  | undefined
  | null
  | { [k: string]: unknown }
  | unknown
> {
  id: string;
  created_at?: string;
  updated_at?: string;
}

export interface BccUserProfile extends DbRecord {
  name: string;
  email: string;
  is_admin: boolean;
}

export interface NewBCCUserInfo extends BccUserProfile {
  password: string;
}

// the possible auth providers and their email domains
export interface AuthProvider extends DbRecord {
  name: string;
  email_domain: string;
}

export interface PaginatedData<T> {
  skip: number;
  limit?: number | null;
  data: T;
}

export interface CountResponse {
  count: number;
}

// the HTTP request body sent when making any kind of request
export interface UserRequestPostBody {
  type: UserRequestType;
  // the project the request concerns; the requester for create-project
  resource_id: string;
  reason: string;
  metadata?: Partial<UserRequestMetadata>;
}

export enum UserRequestStatus {
  APPROVED = "approved",
  REJECTED = "rejected",
  PENDING = "pending",
}

export enum UserRequestType {
  CREATE_PROJECT = "create-project",
  CLOSE_PROJECT = "close-project",
  TRANSFER_PROJECT = "transfer-project",
  PROJECT_QPU_SECONDS = "project-qpu-seconds",
  PROJECT_ACCESS = "project-access",
}

export enum UserRole {
  ADMIN = "admin",
  SYSTEM = "system",
  RESEARCHER = "researcher",
  USER = "user",
  PARTNER = "partner",
}

export enum RqJobStatus {
  CREATED = "created",
  QUEUED = "queued",
  FINISHED = "finished",
  FAILED = "failed",
  STARTED = "started",
  DEFERRED = "deferred",
  SCHEDULED = "scheduled",
  STOPPED = "stopped",
  CANCELED = "canceled",
}

// the most urgent is the lowest, so notices sort by it
export enum NoticeSeverity {
  CRITICAL = 1,
  WARNING = 2,
  INFO = 3,
}

export enum NoticeType {
  PROJECT_ACCESS_REQUESTED = "project-access-requested",
  PROJECT_ACCESS_APPROVED = "project-access-approved",
  PROJECT_ACCESS_REJECTED = "project-access-rejected",
  PROJECT_CREATE_REQUESTED = "project-create-requested",
  PROJECT_CREATE_APPROVED = "project-create-approved",
  PROJECT_CREATE_REJECTED = "project-create-rejected",
  PROJECT_CLOSE_REQUESTED = "project-close-requested",
  PROJECT_CLOSE_APPROVED = "project-close-approved",
  PROJECT_CLOSE_REJECTED = "project-close-rejected",
  PROJECT_TRANSFER_REQUESTED = "project-transfer-requested",
  PROJECT_TRANSFER_APPROVED = "project-transfer-approved",
  PROJECT_TRANSFER_REJECTED = "project-transfer-rejected",
  QPU_SECONDS_REQUESTED = "qpu-seconds-requested",
  QPU_SECONDS_GRANTED = "qpu-seconds-granted",
  QPU_SECONDS_DENIED = "qpu-seconds-denied",
  QPU_SECONDS_LOW = "qpu-seconds-low",
  QPU_SECONDS_DEPLETED = "qpu-seconds-depleted",
  PROJECT_MEMBERSHIP_GRANTED = "project-membership-granted",
  PROJECT_MEMBERSHIP_REVOKED = "project-membership-revoked",
  PROJECT_ADMIN_ASSIGNED = "project-admin-assigned",
  CUSTOM = "custom",
  CUSTOM_BROADCAST = "custom-broadcast",
}

// what a notice refers to, e.g. the request it asks the reader to decide
export enum NoticeRefType {
  USER_REQUEST = "user_request",
  PROJECT = "project",
}
