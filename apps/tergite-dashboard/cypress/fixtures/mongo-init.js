/**
 * Converts a JS object into a BSON-like object
 * @param {Object} obj - the object to convert to document
 * @returns {Object} - a BSON-like document
 */
const toDoc = ({ id, ...props }) => ({ _id: ObjectId(id), ...props });

/**
 * Converts a JS object into a BSON-like object for tokens
 * @param {Object} obj - the object to convert to document
 * @returns {Object} - a BSON-like document
 */
const toTokenDoc = ({ id, user_id, created_at, ...props }) => ({
  _id: ObjectId(id),
  user_id: ObjectId(user_id),
  created_at: ISODate(),
  ...props,
});

/**
 * Converts into a proper Job object
 * @param {Object} obj - the object to convert to document
 * @returns {Object} - a Job object
 */
const toJob = ({ device, status, duration_in_secs, id, ...props }) => {
  let result = null;
  let download_url = null;

  // if the job completed successfully, add the results and the download url
  if (status === "successful") {
    result = {
      memory: [],
    };
    download_url = `http://${device}/logfiles/${id}`;
  }

  let timestamps = null;
  if (duration_in_secs != null) {
    const startDate = new Date();
    const endDate = new Date(startDate);
    endDate.setSeconds(endDate.getSeconds() + duration_in_secs);

    timestamps = {
      registration: null,
      pre_processing: null,
      execution: {
        started: ISODate(startDate.toISOString()),
        finished: ISODate(endDate.toISOString()),
      },
      post_processing: null,
      final: null,
    };
  }

  return {
    id,
    device,
    status,
    timestamps,
    result,
    download_url,
    ...props,
  };
};

db = db.getSiblingDB("testing"); // Create/use database

// Drop the database
db.dropDatabase();
console.log("Database 'testing' dropped successfully.");

console.log("Inserting initial data in mongo...");

// The following raw data will be replaced by JSON from
// fixtures when the tests start
const rawCalibrations = "[]";
const rawDevices = "[]";
const rawJobs = "[]";
const rawProjects = "[]";
const rawTokens = "[]";
const rawUserRequests = "[]";
const rawUsers = "[]";

console.log("Parsing initial documents ....");
// parse the raw results
const calibrations = JSON.parse(rawCalibrations).map(toDoc);
console.log({ calibrations });
const devices = JSON.parse(rawDevices).map(toDoc);
console.log({ devices });
const jobs = JSON.parse(rawJobs).map(toJob).map(toDoc);
console.log({ jobs });
const projects = JSON.parse(rawProjects).map(toDoc);
console.log({ projects });
const tokens = JSON.parse(rawTokens).map(toTokenDoc);
console.log({ tokens });
const userRequests = JSON.parse(rawUserRequests).map(toDoc);
console.log({ userRequests });
const users = JSON.parse(rawUsers).map(toDoc);
console.log({ users });
// bot user for making authenticated requests from BCC to MSS
const botUser = users.find((v) => v.roles.includes("system"));
console.log({ botUser });
const botProject = projects.find(
  (v) =>
    v.user_ids.includes(`${botUser["_id"]}`) && v.qpu_seconds > 1 && v.is_active
);
console.log({ botProject });
const botToken = {
  _id: ObjectId("67bdc2aacd991c8e1cf16ffc"),
  title: "some-token-test",
  project_ext_id: botProject["ext_id"],
  lifespan_seconds: 7200000,
  token: "W0imS_n_J5ZwP8wFYvbBCiDkJVhQcEROEfyTPvFko1E",
  user_id: botUser["_id"],
  created_at: ISODate(),
};
console.log({ systemToken: botToken });

db.auth_projects.insertMany(projects);
console.log("Inserted projects");
db.auth_app_tokens.insertMany([...tokens, botToken]);
console.log("Inserted tokens");
db.auth_users.insertMany(users);
console.log("Inserted users");
db.calibrations.insertMany(calibrations);
console.log("Inserted calibrations");
db.devices.insertMany(devices);
console.log("Inserted devices");
db.jobs.insertMany(jobs);
console.log("Inserted jobs");
db.auth_user_requests.insertMany(userRequests);
console.log("Inserted user requests");
