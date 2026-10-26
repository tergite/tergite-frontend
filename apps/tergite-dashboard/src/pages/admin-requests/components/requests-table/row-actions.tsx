import { Button } from "@/components/ui/button";
import {
  approveMyRequest,
  refreshDecisionQueries,
  rejectMyRequest,
} from "@/lib/api/requests";
import { ReloadIcon } from "@radix-ui/react-icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  UserRequestStatus,
  type UserRequest,
} from "../../../../../types";

export function RowActions({ request }: Props) {
  const queryClient = useQueryClient();

  const approval = useMutation({
    mutationFn: approveMyRequest,
    onSuccess: async () => await refreshDecisionQueries(queryClient),
    throwOnError: true,
  });

  const rejection = useMutation({
    mutationFn: rejectMyRequest,
    onSuccess: async () => await refreshDecisionQueries(queryClient),
    throwOnError: true,
  });

  if (request.status !== UserRequestStatus.PENDING) {
    return null;
  }

  const isPending = approval.isPending || rejection.isPending;

  return (
    // clicking a row opens the detail panel, which is not what these mean
    <div className="flex gap-2" onClick={(ev) => ev.stopPropagation()}>
      <Button
        type="button"
        size="sm"
        data-cy-row-approve
        disabled={isPending}
        onClick={() => approval.mutate(request.id)}
      >
        {approval.isPending && (
          <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
        )}
        Approve
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="text-destructive border-destructive"
        data-cy-row-reject
        disabled={isPending}
        onClick={() => rejection.mutate({ id: request.id })}
      >
        {rejection.isPending && (
          <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
        )}
        Reject
      </Button>
    </div>
  );
}

interface Props {
  request: UserRequest;
}
