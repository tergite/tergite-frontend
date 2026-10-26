import { DateTime } from "luxon";
import {
  AnyFlatRecord,
  AppToken,
  ExtendedAppToken,
  Project,
  UserRequest,
} from "../../dev/mock-api/types";

/**
 * Converts an AppToken instance to an ExtendedAppToken instance
 *
 * It computes the computed properties
 *
 * @param token - the AppToken instance
 * @param project - the project it is attached the app token is attached to
 */
export function extendAppToken(
  token: AppToken,
  project: Project
): ExtendedAppToken {
  const expires_at = DateTime.fromISO(token.created_at).plus({
    seconds: token.lifespan_seconds,
  });
  const is_expired = DateTime.now() > expires_at;
  const project_name = project.name;

  return { ...token, expires_at, is_expired, project_name };
}

/**
 * Gets the details of the user request shown in its summary, i.e. its reason and
 * its non-empty metadata other than the resource
 *
 * @param request - the request whose details are to be obtained
 */
export function getUserRequestDetails(request: UserRequest): AnyFlatRecord {
  const { resource: _resource, ...metadata } = request.metadata;
  return Object.fromEntries(
    Object.entries({ reason: request.reason, ...metadata }).filter(
      ([_k, v]) => v != null
    )
  );
}
