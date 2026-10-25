import createClient from "openapi-fetch";
import type { ErrorInfo } from "../../../types";
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
  const error = new Error(parseDetail(text)) as ErrorInfo;
  error.status = response.status;
  return error;
}

function parseDetail(text: string): string {
  try {
    const { detail } = JSON.parse(text);
    return typeof detail === "string" ? detail : text;
  } catch {
    return text;
  }
}
