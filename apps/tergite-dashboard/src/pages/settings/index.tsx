import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { noticePreferencesQuery } from "@/lib/api/notices";
import { loadOrRedirectIfAuthErr } from "@/lib/utils";
import { QueryClient } from "@tanstack/react-query";
import { type AppState } from "types";
import { NotificationPreferencesForm } from "./components/notification-preferences-form";

export function Settings() {
  return (
    <main className="grid flex-1 items-start gap-4 p-4 sm:px-6 sm:py-0 max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>Email notifications</CardTitle>
          <CardDescription>
            Anything awaiting your action always shows in the dashboard; these
            switches only decide whether it is also emailed to you.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <NotificationPreferencesForm />
        </CardContent>
      </Card>
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(_appState: AppState, queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async () => {
    await queryClient.ensureQueryData(noticePreferencesQuery);
    return {};
  });
}
