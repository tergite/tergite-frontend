import {
  DataTag,
  QueryClient,
  QueryKey,
  UndefinedInitialDataOptions,
} from "@tanstack/react-query";
import { LoaderFunction, LoaderFunctionArgs, redirect } from "react-router-dom";

/** Wraps a loader so that a 401 redirects to the login page and a 403 to home */
export function loadOrRedirectIfAuthErr(loaderFn: LoaderFunction) {
  return async (params: LoaderFunctionArgs) => {
    try {
      return await loaderFn(params);
    } catch (error) {
      // @ts-expect-error error can be any
      if (error.status === 401) {
        return redirect("/login");
      }

      // @ts-expect-error error can be any
      if (error.status === 403) {
        return redirect("/");
      }

      throw error;
    }
  };
}

/** Fetches the query's list, or an empty one where it fails and must not throw */
export async function tryQueryFetchMany<T, K extends QueryKey = QueryKey>(
  client: QueryClient,
  options: UndefinedInitialDataOptions<T[], Error, T[], K> & {
    queryKey: DataTag<K, T[]>;
  },
) {
  try {
    return await client.ensureQueryData(options);
  } catch (error) {
    if (options.throwOnError) {
      throw error;
    }
    return [];
  }
}
