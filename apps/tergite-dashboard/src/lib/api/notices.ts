import {
  keepPreviousData,
  QueryClient,
  queryOptions,
} from "@tanstack/react-query";
import type {
  GeneralMessage,
  Notice,
  NoticePostRequest,
  NoticePreferences,
} from "./types";
import { client } from "./client";
import type { paths } from "./schema";
import type { NoticeType } from "./types";

// the admin-authored notices, as opposed to those the system emits on events
export const CUSTOM_NOTICE_TYPES: NoticeType[] = ["custom", "custom-broadcast"];

type AdminNoticesQuery = NonNullable<
  paths["/admin/notices"]["get"]["parameters"]["query"]
>;
type NoticeCountQuery = NonNullable<
  paths["/counts/notices"]["get"]["parameters"]["query"]
>;
type MyNoticesQuery = NonNullable<
  paths["/me/notices/"]["get"]["parameters"]["query"]
>;

export function getNoticesQuery(query: AdminNoticesQuery = {}) {
  return queryOptions({
    queryKey: ["admin", "notices", query],
    queryFn: async () => {
      const { data } = await client.GET("/admin/notices", {
        params: { query },
      });
      return data!.data as Notice[];
    },
    throwOnError: true,
    placeholderData: keepPreviousData,
  });
}

export function getNoticeCountQuery(query: NoticeCountQuery = {}) {
  return queryOptions({
    queryKey: ["counts", "notices", query],
    queryFn: async () => {
      const { data } = await client.GET("/counts/notices", {
        params: { query },
      });
      return data!.count;
    },
    throwOnError: true,
  });
}

/** The current user's notices, newest first */
export function getMyNoticesQuery(query: MyNoticesQuery = {}) {
  return queryOptions({
    queryKey: ["me", "notices", query],
    queryFn: async () => {
      const { data } = await client.GET("/me/notices/", {
        params: { query },
      });
      return data!.data as Notice[];
    },
    // no polling: the count badge is what needs to stay fresh, and the list
    // refetches when the panel opens and after any reaction
    refetchInterval: false,
    throwOnError: true,
    placeholderData: keepPreviousData,
  });
}

/** Which notice types the current user also gets by email */
export const noticePreferencesQuery = queryOptions({
  queryKey: ["me", "notices", "preferences"],
  queryFn: async () => {
    const { data } = await client.GET("/me/notices/preferences/");
    return data! as NoticePreferences;
  },
  refetchInterval: false,
  throwOnError: true,
});

/** @returns one notice per targeted user, or the one notice for all users */
export async function createNotice(
  payload: NoticePostRequest,
): Promise<Notice[]> {
  const { data } = await client.POST("/admin/notices/", { body: payload });
  return data! as Notice[];
}

export async function deleteNotice(id: string): Promise<void> {
  await client.DELETE("/admin/notices/{notice_id}", {
    params: { path: { notice_id: id } },
  });
}

export async function dismissNotice(id: string): Promise<GeneralMessage> {
  const { data } = await client.POST("/me/notices/{notice_id}/dismiss", {
    params: { path: { notice_id: id } },
  });
  return data!;
}

export async function dismissAllMyNotices(): Promise<GeneralMessage> {
  const { data } = await client.POST("/me/notices/dismiss");
  return data!;
}

/** Sets whether the named notice types are also emailed, leaving the rest untouched */
export async function updateNoticePreferences(
  payload: Partial<NoticePreferences>,
): Promise<NoticePreferences> {
  const { data } = await client.PUT("/me/notices/preferences/", {
    body: payload,
  });
  return data! as NoticePreferences;
}

export function refreshAllNotices(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: ["admin", "notices"] });
}

export function refreshAllNoticeCounts(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: ["counts", "notices"] });
}

export async function refreshMyNotices(queryClient: QueryClient) {
  await queryClient.invalidateQueries({ queryKey: ["me", "notices"] });
  await refreshAllNoticeCounts(queryClient);
}
