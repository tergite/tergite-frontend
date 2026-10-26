import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { DetailItem } from "@/components/ui/detail-item";
import {
  approveMyRequest,
  refreshDecisionQueries,
  rejectMyRequest,
} from "@/lib/api/requests";
import { cn } from "@/lib/utils";
import { getUserRequestDetails, getUserRequestTitle } from "@/lib/user-requests";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnyValue, type UserRequest } from "types";
import { Separator } from "@/components/ui/separator";
import { ProgressStatus } from "@/components/ui/progress-status";
import { DateTime } from "luxon";
import { Button } from "@/components/ui/button";
import { ReloadIcon } from "@radix-ui/react-icons";
import { useMemo } from "react";
import { SidebarPlaceholder } from "@/components/ui/sidebar-placeholder";

export function RequestsSidebar(props: SidebarProps) {
  return props.request ? (
    <RequestSummary {...(props as RequestSummaryProps)} />
  ) : (
    <SidebarPlaceholder
      mainTitle="User request title"
      contentTitle="Request details"
      contentDetail="Click any row to show details here"
      className={props.className}
    />
  );
}

function RequestSummary({
  request,
  className = "",
  onApproval,
  onRejection,
}: RequestSummaryProps) {
  const queryClient = useQueryClient();
  const requestApproval = useMutation({
    mutationFn: approveMyRequest,
    onSuccess: async () => {
      // before the refresh, or it would clear a row picked meanwhile
      onApproval(request.id);
      await refreshDecisionQueries(queryClient);
    },
    throwOnError: true,
  });

  const requestRejection = useMutation({
    mutationFn: rejectMyRequest,
    onSuccess: async () => {
      onRejection(request.id);
      await refreshDecisionQueries(queryClient);
    },
    throwOnError: true,
  });

  const requestTitle = useMemo(() => getUserRequestTitle(request), [request]);
  const isResponsePending =
    requestApproval.isPending || requestRejection.isPending;

  return (
    <Card id="request-summary" className={cn("overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-start bg-muted/50 justify-between">
        <div className="grid gap-0.5">
          <CardTitle className="group flex items-center gap-2 text-lg">
            {requestTitle}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-6 text-sm">
        <div data-cy-request-body className="grid gap-3">
          <div className="font-semibold">Request</div>
          <ul className="grid gap-3">
            {Object.entries(getUserRequestDetails(request)).map(
              ([key, value]) => (
                <DetailItem label={toUserFriendlyProp(key)}>
                  {toString(value)}
                </DetailItem>
              )
            )}
          </ul>
        </div>
        <Separator className="my-4" />
        <div data-cy-additional-information className="grid gap-3">
          <div className="font-semibold">Additional information</div>
          <ul className="grid gap-3">
            <DetailItem label="Requested by">
              {request.requester_name}
            </DetailItem>

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

            {request.approver_name && (
              <DetailItem label="Approved by">
                {request.approver_name}
              </DetailItem>
            )}

            <DetailItem label="Created">
              {DateTime.fromISO(request.created_at).toRelative()}
            </DetailItem>
          </ul>
        </div>
      </CardContent>
      <CardFooter className="flex flex-row items-center border-t bg-muted/50 px-6 py-3">
        <div className="grid grid-cols-2 gap-2 w-full">
          <Button
            type="button"
            variant="default"
            onClick={() => requestApproval.mutate(request.id)}
            disabled={isResponsePending}
          >
            {requestApproval.isPending && (
              <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
            )}
            Approve
          </Button>
          <Button
            type="button"
            variant="outline"
            className="text-destructive border-destructive"
            onClick={() => requestRejection.mutate({ id: request.id })}
            disabled={isResponsePending}
          >
            {requestRejection.isPending && (
              <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
            )}
            Reject
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}

interface SidebarProps {
  request?: UserRequest;
  className?: string;
  onApproval: (id: string) => void;
  onRejection: (id: string) => void;
}

interface RequestSummaryProps extends SidebarProps {
  request: UserRequest;
}

/**
 * Converts a property name into something that is more user friendly
 *
 * @param propName - the property name
 * @returns the user friendly version of the property name
 */
function toUserFriendlyProp(propName: string): string {
  const result = propName.replace(/_|-/g, " ");
  return result.charAt(0).toUpperCase().concat(result.slice(1));
}

/**
 * Converts a property value into something that is more user friendly
 *
 * @param value - the property value
 * @returns the user friendly version of the property value
 */
function toString(value: AnyValue): string {
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return `${value}`;
}
