import { DateTime } from "luxon";

export type AnyValue = number | string | null | undefined | number[] | string[];

export type AnyFlatRecord = Record<string, AnyValue>;

export enum JobStatus {
  PENDING = "pending",
  SUCCESSFUL = "successful",
  FAILED = "failed",
  EXECUTING = "executing",
}

export interface DbRecord {
  id: string;
  created_at?: string;
  updated_at?: string;
}

export enum QubitProp {
  T1_DECOHERENCE = "t1_decoherence",
  T2_DECOHERENCE = "t2_decoherence",
  FREQUENCY = "frequency",
  ANHARMONICITY = "anharmonicity",
  READOUT_ASSIGNMENT_ERROR = "readout_assignment_error",
}

export interface Qubit {
  t1_decoherence?: CalibrationValue;
  t2_decoherence?: CalibrationValue;
  frequency?: CalibrationValue;
  anharmonicity?: CalibrationValue;
  readout_assignment_error?: CalibrationValue;
  pi_pulse_amplitude?: CalibrationValue;
  pi_pulse_duration?: CalibrationValue;
  pulse_type?: CalibrationValue;
  pulse_sigma?: CalibrationValue;
  index?: CalibrationValue;
  x_position?: CalibrationValue;
  y_position?: CalibrationValue;
  xy_drive_line: CalibrationValue;
  z_drive_line?: CalibrationValue;
  [k: string]: CalibrationValue | undefined | null;
}

/**
 * Tuned properties of the device that change on recalibration/tune up
 * These will most likely have a datetime when they were generated.
 *
 * This can allow us to debug jobs that used run through
 * the device a multiple calibrations in the past
 */
export interface DeviceCalibration extends Omit<DbRecord, "created_at"> {
  name: string;
  version: string;
  qubits: Qubit[];
  last_calibrated: string;
}

export interface CalibrationValue {
  date?: string;
  unit: "ns" | "us" | "GHz" | "MHz" | "" | "s" | "Hz";
  value: number;
}

export interface CalibrationDataPoint extends Partial<CalibrationValue> {
  index: number;
}

export type AggregateValue = Omit<CalibrationValue, "date">;

export interface DeviceCalibrationMedians {
  t1_decoherence?: AggregateValue;
  t2_decoherence?: AggregateValue;
  readout_assignment_error?: AggregateValue;
}

/**
 * Properties of the device that are more or less static
 */
export interface Device extends DbRecord {
  name: string;
  version: string;
  number_of_qubits: number;
  last_online: string | null | undefined;
  is_online: boolean;
  basis_gates: string[];
  /**
   * this maps what qubit is connected to which other qubit. Indexes not names are used here.
   * This is bi-directional
   */
  coupling_map: [number, number][];
  // a dictionary of couple channel and qubit names in string form
  coupling_dict: { [key: string]: [string, string] } | undefined;
  // a map of qubit pair (ids e.g. q12 -> 12) and coupler in int form
  qubit_ids_coupler_map: [[number, number], number][] | undefined;
  /**
   * the coordinates of for each qubit, where the index is the qubit
   */
  coordinates: [number, number][];
  is_simulator: boolean;
  // List of qubit ids in order
  qubit_ids: string[];
  characterized?: boolean;
  open_pulse?: boolean;
  meas_map?: number[][];
  description?: string;
  number_of_couplers?: number;
  number_of_resonators?: number;
  dt?: number;
  dtm?: number;
  meas_lo_freq?: number[];
  qubit_lo_freq?: number[];
  gates?: { [key: string]: unknown };
  is_active?: boolean;
}

/**
 * Properties of the bookings
 */
export interface NewBookingInfo {
  start_utc: string;
  end_utc: string;
}

export interface Booking extends NewBookingInfo {
  id: string;
  total_duration: number;
  user_id?: string;
  username?: string;
}

export interface BccUserProfile {
  id: string;
  name: string;
  email: string;
  is_admin: boolean;
}

export interface NewBCCUserInfo extends BccUserProfile {
  password: string;
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
}

// the type for all requests made by users to be approved by an admin
export interface UserRequest extends DbRecord {
  created_at: string;
  updated_at: string;
  status: UserRequestStatus;
  type: UserRequestType;
  requester_id: string;
  requester_name?: string;
  approver_id?: string; // id of admin who has handled it
  approver_name?: string;
  rejection_reason?: string;
  request: unknown;
}

// the HTTP request body sent when creating a project.
// it ends up as a new Project
export interface CreateProjectPostBody {
  name: string;
  ext_id: string;
  description?: string;
  user_emails: string[];
  qpu_seconds: number;
}

// An approval is created in the database with given data
// but a new project is only created in the database using this data
// after approval is given.
//
// the type below is of that request
export interface CreateProjectUserRequest extends UserRequest {
  type: UserRequestType.CREATE_PROJECT;
  request: CreateProjectPostBody;
}

// the HTTP response body got when a project is got from API
export interface Project
  extends Omit<CreateProjectPostBody, "user_emails">,
    DbRecord {
  user_ids: string[];
  admin_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// the enhanced response an admin user sees when looking at a project
export interface AdminProject extends Project {
  user_emails: string[];
  admin_email: string;
}

// the HTTP request body when updating a project
export interface UpdateProjectPutBody
  extends Partial<Omit<CreateProjectPostBody, "ext_id">> {
  admin_email?: string;
  is_active?: boolean;
}

// the HTTP request body when creating a project as admin
export interface AdminCreateProjectBody extends CreateProjectPostBody {
  admin_email: string;
}

// the HTTP request body when requesting for a time extension
export interface QpuTimeExtensionPostBody {
  project_id: string;
  project_name?: string;
  seconds: number;
  reason: string;
}

// the record saved in the database for QPU time extension
export interface QpuTimeExtensionUserRequest extends UserRequest {
  type: UserRequestType.PROJECT_QPU_SECONDS;
  request: QpuTimeExtensionPostBody;
}

export interface Job extends DbRecord {
  job_id: string;
  project_id?: string;
  user_id?: string;
  device: string;
  status: JobStatus;
  failure_reason?: string;
  duration_in_secs?: number;
  created_at: string;
}

export enum UserRole {
  ADMIN = "admin",
  SYSTEM = "system",
  RESEARCHER = "researcher",
  USER = "user",
  PARTNER = "partner",
}

export interface User extends DbRecord {
  roles: UserRole[];
  email: string;
  organization?: string;
}

export interface AppToken extends DbRecord {
  title: string;
  user_id: string;
  project_ext_id: string;
  lifespan_seconds: number;
  created_at: string;
}

// an extension of the AppToken schema with some computed properties
export interface ExtendedAppToken extends AppToken {
  expires_at: DateTime;
  is_expired: boolean;
  project_name: string;
}

// the HTTP request body for creating an app token
export interface AppTokenCreationRequest {
  title: string;
  project_ext_id: string;
  lifespan_seconds: number;
}

// the HTTP response body after the creation of the app token
export interface AppTokenCreationResponse {
  access_token: string;
  token_type: string;
}

// the HTTP request body for updating an app token
export interface AppTokenUpdateRequest {
  expires_at: string;
}

// the possible auth providers and their email domains
export interface AuthProvider extends DbRecord {
  name: string;
  email_domain: string;
}

// the response from the API detailing the URL to redirect to for authentication
export interface Oauth2RedirectResponse {
  authorization_url: string;
}

// the response from the API detailing the URL to login for the given email domain
export interface AuthProviderResponse {
  url: string;
  name: string;
}

export interface AppState {
  currentProjectExtId?: string;
  setCurrentProjectExtId: (value?: string) => void;
  apiToken?: string;
  setApiToken: (value?: string) => void;
  clear: () => void;
  isDark?: boolean;
  toggleIsDark: () => void;
}

export interface ErrorInfo extends Error {
  status?: number;
  statusText?: string;
}

export interface PaginatedData<T> {
  skip: number;
  limit?: number | null;
  data: T;
}

export interface Time {
  hour?: number;
  minute?: number;
  second?: number;
  millisecond?: number;
}

export interface Duration {
  days?: number;
  hours?: number;
  minutes?: number;
  seconds?: number;
  milliseconds?: number;
}
