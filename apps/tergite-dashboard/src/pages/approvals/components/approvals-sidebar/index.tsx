import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DetailItem } from "@/components/ui/detail-item";
import { ProgressStatus } from "@/components/ui/progress-status";
import { Separator } from "@/components/ui/separator";
import { SidebarPlaceholder } from "@/components/ui/sidebar-placeholder";
import { approveMyRequest, rejectMyRequest } from "@/lib/api-client";
import { cn, getUserRequestTitle } from "@/lib/utils";
import { ReloadIcon } from "@radix-ui/react-icons";
import { useMutation } from "@tanstack/react-query";
import { DateTime } from "luxon";
import { useMemo } from "react";
import {
  AnyFlatRecord,
  AnyValue,
  UserRequestStatus,
  type UserRequest,
} from "../../../../../types";

export function ApprovalsSidebar(props: SidebarProps) {
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

function RequestSummary({
  request,
  className = "",
  onReaction,
}: RequestSummaryProps) {
  const approval = useMutation({
    mutationFn: approveMyRequest,
    onSuccess: async () => await onReaction(),
    throwOnError: true,
  });

  const rejection = useMutation({
    mutationFn: rejectMyRequest,
    onSuccess: async () => await onReaction(),
    throwOnError: true,
  });

  const title = useMemo(() => getUserRequestTitle(request), [request]);
  const isPending = approval.isPending || rejection.isPending;
  const isDecided = request.status !== UserRequestStatus.PENDING;

  return (
    <Card id="approval-summary" className={cn("overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-start bg-muted/50 justify-between">
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-6 text-sm">
        <div data-cy-request-body className="grid gap-3">
          <div className="font-semibold">Request</div>
          <ul className="grid gap-3">
            {Object.entries(request.request as AnyFlatRecord).map(
              ([key, value]) => (
                <DetailItem key={key} label={toUserFriendlyProp(key)}>
                  {toString(value)}
                </DetailItem>
              ),
            )}
          </ul>
        </div>
        <Separator className="my-4" />
        <ul className="grid gap-3">
          <DetailItem label="From">{request.requester_name}</DetailItem>
          <DetailItem label="Status">
            <ProgressStatus
              status={request.status}
              pendingValue="pending"
              successValue="approved"
              failureValue="rejected"
            />
          </DetailItem>
          {request.rejection_reason && (
            <DetailItem label="Reason">{request.rejection_reason}</DetailItem>
          )}
          <DetailItem label="Created">
            {DateTime.fromISO(request.created_at).toRelative()}
          </DetailItem>
        </ul>
      </CardContent>
      {!isDecided && (
        <CardFooter className="flex flex-row items-center border-t bg-muted/50 px-6 py-3">
          <div className="grid grid-cols-2 gap-2 w-full">
            <Button
              type="button"
              data-cy-approve
              onClick={() => approval.mutate(request.id)}
              disabled={isPending}
            >
              {approval.isPending && (
                <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
              )}
              Approve
            </Button>
            <Button
              type="button"
              variant="outline"
              data-cy-reject
              className="text-destructive border-destructive"
              onClick={() => rejection.mutate({ id: request.id })}
              disabled={isPending}
            >
              {rejection.isPending && (
                <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
              )}
              Reject
            </Button>
          </div>
        </CardFooter>
      )}
    </Card>
  );
}

interface SidebarProps {
  request?: UserRequest;
  className?: string;
  onReaction: () => Promise<void>;
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
