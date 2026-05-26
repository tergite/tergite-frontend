import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Notice, NoticeSeverity } from "../../../../../types";
import { NoticeBanner } from "@/components/ui/notice-banner";
import NoticeForm from "./form";
import { SEVERITY_LABELS } from "@/lib/utils";

const SEVERITY_TEXT_CLASSES: Record<NoticeSeverity, string> = {
  [NoticeSeverity.INFO]: "text-blue-700 dark:text-blue-300",
  [NoticeSeverity.WARNING]: "text-yellow-700 dark:text-yellow-300",
  [NoticeSeverity.CRITICAL]: "text-red-700 dark:text-red-300",
};


export function NoticesCard({ items, isAdmin }: Props) {

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardDescription>Notices</CardDescription>
        <div className="flex items-center justify-between">
          {/* <p className="text-base font-medium">All users</p> */}
          {items.length > 0 && (
            <Badge variant="secondary">{items.length} active</Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {/* Active banners */}
        {items.length === 0 ? (
          <div className="rounded-md border border-dashed p-3 text-center">
            <p className="text-sm text-muted-foreground">
              No active notices
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {items.map((notice) => (
              <NoticeBanner
                key={notice.id}
                notice={notice}
                isAdmin={isAdmin}
              />
            ))}
          </div>
        )}

        <NoticeForm />

        {/* History */}
        {items.slice(1).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
              History ({items.length})
            </p>
            <div className="flex flex-col gap-1.5 max-h-28 overflow-y-auto">
              {items.map((notice) => (
                <div
                  key={notice.id}
                  className="text-xs text-muted-foreground bg-muted/40 rounded px-2 py-1.5 truncate"
                >
                  <span
                    className={`font-medium ${SEVERITY_TEXT_CLASSES[notice.severity]}`}
                  >
                    {SEVERITY_LABELS[notice.severity]}
                  </span>{" "}
                  · {notice.message}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}


interface Props {
  items: Notice[];
  isAdmin: boolean;
}
