import { DateTime } from "luxon";
import type { AppToken, Project } from "./api/types";

// apart from api/tokens.ts, which builds the HTTP client, so that the Playwright specs can load it

/** Names each token's project, leaving out the tokens of projects not in the list */
export function addProjectNames(
  tokens: AppToken[],
  projects: Project[],
): ExtendedAppToken[] {
  const projectMap = Object.fromEntries(projects.map((v) => [v.id, v]));
  return tokens
    .filter((v) => projectMap[v.project_id])
    .map((v) => extendAppToken(v, projectMap[v.project_id]));
}

export function extendAppToken(
  token: AppToken,
  project: Project,
): ExtendedAppToken {
  const expires_at = DateTime.fromISO(token.created_at).plus({
    seconds: token.lifespan_seconds,
  });
  const is_expired = DateTime.now() > expires_at;
  return { ...token, expires_at, is_expired, project_name: project.name };
}

export type ExtendedAppToken = AppToken & {
  expires_at: DateTime;
  is_expired: boolean;
  project_name: string;
};
