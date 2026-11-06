import createClient from "openapi-fetch";
import type { paths } from "./schema";

// every non-2xx response throws in the middleware below, so a call that returns has its data
export const client = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL,
  credentials: "include",
});

client.use({
  async onResponse({ response }) {
    if (!response.ok) throw await getErrorInfo(response);
  },
});

async function getErrorInfo(response: Response): Promise<ErrorInfo> {
  const text = await response.text();
  const detail = parseDetail(text);
  const error = new Error(formatDetail(detail, text)) as ErrorInfo;
  error.status = response.status;
  error.detail = detail;
  return error;
}

function parseDetail(text: string): unknown {
  try {
    return JSON.parse(text).detail;
  } catch {
    return undefined;
  }
}

/** The detail as a sentence: as given, or a validation error's messages joined */
function formatDetail(detail: unknown, text: string): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (
    Array.isArray(detail) &&
    detail.every((v) => typeof v?.msg === "string")
  ) {
    return detail.map((v) => v.msg).join("; ");
  }
  return text;
}

export type ErrorInfo = Error & {
  status?: number;
  statusText?: string;
  // the response's detail as MSS sent it, e.g. a 422's list of errors
  detail?: unknown;
};
