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
import { cn, getUserRequestDetails, getUserRequestTitle } from "@/lib/utils";
import { DateTime } from "luxon";
import { useMemo } from "react";
import {
  AnyValue,
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
        <div data-cy-request-body className="grid gap-3">
          <div className="font-semibold">Request</div>
          <ul className="grid gap-3">
            {Object.entries(getUserRequestDetails(request)).map(
              ([key, value]) => (
                <DetailItem key={key} label={toUserFriendlyProp(key)}>
                  {toString(value)}
                </DetailItem>
              )
            )}
          </ul>
        </div>
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

/**
 * Converts a property name into something more user friendly
 *
 * @param propName - the property name
 */
function toUserFriendlyProp(propName: string): string {
  const result = propName.replace(/_|-/g, " ");
  return result.charAt(0).toUpperCase().concat(result.slice(1));
}

/**
 * Converts a property value into something more user friendly
 *
 * @param value - the property value
 */
function toString(value: AnyValue): string {
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return `${value}`;
}
