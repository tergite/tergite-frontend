import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DetailItem } from "@/components/ui/detail-item";
import { ProgressStatus } from "@/components/ui/progress-status";
import { Separator } from "@/components/ui/separator";
import { SidebarPlaceholder } from "@/components/ui/sidebar-placeholder";
import { cn } from "@/lib/utils";
import { getUserRequestTitle } from "@/lib/user-requests";
import { RequestDetails } from "@/components/ui/request-details";
import { DateTime } from "luxon";
import { useMemo } from "react";
import {
  type UserRequest,
} from "../../../../../types";

export function MyRequestSidebar(props: SidebarProps) {
  return props.request ? (
    <RequestSummary {...(props as RequestSummaryProps)} />
  ) : (
    <SidebarPlaceholder
      mainTitle="Request"
      contentTitle="Request details"
      contentDetail="Click any row to show details here"
      className={props.className}
    />
  );
}

function RequestSummary({ request, className = "" }: RequestSummaryProps) {
  const title = useMemo(() => getUserRequestTitle(request), [request]);

  return (
    <Card id="request-summary" className={cn("overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-start bg-muted/50 justify-between">
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-6 text-sm">
        <RequestDetails request={request} />
        <Separator className="my-4" />
        <ul className="grid gap-3">
          <DetailItem label="Status">
            <ProgressStatus
              status={request.status}
              pendingValue="pending"
              successValue="approved"
              failureValue="rejected"
            />
          </DetailItem>
          {request.approver_name && (
            <DetailItem label="Decided by">{request.approver_name}</DetailItem>
          )}
          {request.rejection_reason && (
            <DetailItem label="Reason">{request.rejection_reason}</DetailItem>
          )}
          <DetailItem label="Created">
            {DateTime.fromISO(request.created_at).toRelative()}
          </DetailItem>
        </ul>
      </CardContent>
    </Card>
  );
}

interface SidebarProps {
  request?: UserRequest;
  className?: string;
}

interface RequestSummaryProps extends SidebarProps {
  request: UserRequest;
}
