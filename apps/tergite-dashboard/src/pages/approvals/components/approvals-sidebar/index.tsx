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
import {
  approveMyRequest,
  refreshDecisionQueries,
  rejectMyRequest,
} from "@/lib/api/requests";
import { cn } from "@/lib/utils";
import { getUserRequestTitle } from "@/lib/user-requests";
import { RequestDetails } from "@/components/ui/request-details";
import { ReloadIcon } from "@radix-ui/react-icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DateTime } from "luxon";
import { useMemo } from "react";
import type { UserRequest } from "@/lib/api/types";

export function ApprovalSummary({
  request,
  className = "",
  onReaction,
}: Props) {
  const queryClient = useQueryClient();
  const handleSuccess = async () => {
    // before the refresh, or it would clear a row picked meanwhile
    onReaction();
    await refreshDecisionQueries(queryClient);
  };
  const approval = useMutation({
    mutationFn: approveMyRequest,
    onSuccess: handleSuccess,
    throwOnError: true,
  });

  const rejection = useMutation({
    mutationFn: rejectMyRequest,
    onSuccess: handleSuccess,
    throwOnError: true,
  });

  const title = useMemo(() => getUserRequestTitle(request), [request]);
  const isPending = approval.isPending || rejection.isPending;
  const isDecided = request.status !== "pending";

  return (
    <Card id="approval-summary" className={cn("overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-start bg-muted/50 justify-between">
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-6 text-sm">
        <RequestDetails request={request} />
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

interface Props {
  request: UserRequest;
  className?: string;
  onReaction: () => void;
}
