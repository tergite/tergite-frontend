import type {
  AnyFlatRecord,
  ExtendedUserRequest,
  UserRequest,
} from "../../types";

/** A title for the request, naming its project where the viewer can see it */
export function getUserRequestTitle(request: ExtendedUserRequest): string {
  const projectName = request.project_name ?? request.resource_id;
  switch (request.type) {
    case "close-project":
      return `Close project '${projectName}'`;
    case "create-project":
      return `Create new project '${request.metadata.name}'`;
    case "project-qpu-seconds":
      return `Add QPU time on project: '${projectName}'`;
    case "project-access":
      return `Join project '${projectName}'`;
    case "transfer-project":
      return `Transfer project '${projectName}'`;
    default:
      return "User request";
  }
}

/** The request's reason and the non-empty details peculiar to its type */
export function getUserRequestDetails(request: UserRequest): AnyFlatRecord {
  // every request concerns a project for now, so the resource says nothing
  const { resource: _resource, ...metadata } = request.metadata;
  const details = { reason: request.reason, ...metadata };
  return Object.fromEntries(
    Object.entries(details).filter(([_k, v]) => v != null),
  );
}
