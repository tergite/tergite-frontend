import type { components } from "./schema";

// the dashboard's names for MSS's schemas, so that a renamed schema is renamed here alone
type Schemas = components["schemas"];
// MSS fills in a stored record's id and creation time, though its schema marks them optional
type Stored<T> = T & { id: string; created_at: string };

export type Device = Schemas["Device"];
export type DeviceCalibration = Schemas["DeviceCalibration"];
export type Qubit = Schemas["QubitCalibration"];
export type CalibrationValue = Schemas["CalibrationValue"];

export type Job = Stored<Schemas["Job"]>;
export type JobStatus = Schemas["JobStatus"];

export type Project = Schemas["ProjectRead"];
export type AdminProject = Schemas["ProjectAdminView"];
export type AdminCreateProjectBody = Schemas["ProjectCreate"];
export type UpdateProjectPutBody = Schemas["ProjectUpdate"];

export type AppToken = Schemas["AppTokenRead"];
export type AppTokenCreationRequest = Schemas["AppTokenCreate"];
export type AppTokenCreationResponse = Schemas["BearerResponse"];
export type AppTokenUpdateRequest = Schemas["AppTokenUpdate"];

export type User = Schemas["UserRead"];
export type UserRole = Schemas["UserRole"];
export type AuthProviderResponse = Schemas["AuthProvider"];

export type Booking = Schemas["Booking"];
export type NewBookingInfo = Schemas["NewBookingInfo"];
export type BookingsConfig = Schemas["BookingsConfig"];

export type GeneralMessage = Schemas["GeneralMessage"];
export type RecalibrationInfo = Schemas["RecalibrationInfo"];
export type RqJobStatus = Schemas["RqJobStatus"];

export type UserRequestStatus = Schemas["RequestStatus"];
export type UserRequestType = Schemas["RequestType"];
// MSS types a request's metadata by the request's type, which its schema cannot say
export type UserRequestMetadata = Schemas["RequestMetadata"] & {
  seconds?: number;
  admin_email?: string;
  name?: string;
  description?: string;
  qpu_seconds?: number;
  user_emails?: string[];
};
export type UserRequest = Stored<Omit<Schemas["Request"], "metadata">> & {
  metadata?: UserRequestMetadata | null;
};

export type Notice = Stored<Schemas["Notice"]>;
export type NoticeType = Schemas["NoticeTypeId"];
export type NoticeSeverity = Schemas["NoticeSeverity"];
export type NoticePostRequest = Schemas["CustomNoticeCreate"];
// the schema says only a map of booleans; MSS keys it by every notice type
export type NoticePreferences = Record<NoticeType, boolean>;
