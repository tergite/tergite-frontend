import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import { refreshMyRequests, requestPulseAccess } from "@/lib/api/requests";
import type { Project, UserRequest } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

const formSchema = z.object({
  reason: z.string().min(1),
});

/**
 * A button that asks the system admins to let a project run pulse-level jobs,
 * disabled while such a request on the project is pending
 */
export function PulseAccessRequestDialog({
  project,
  requests,
  className = "",
}: Props) {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { reason: "" },
  });
  const pendingRequest = useMemo(
    () =>
      requests.find(
        (v) =>
          v.type === "project-pulse-access" &&
          v.resource_id === project.id &&
          v.status === "pending"
      ),
    [requests, project]
  );

  const pulseAccess = useMutation({
    mutationKey: ["me", "projects", project.id, "request-pulse-access"],
    mutationFn: useCallback(
      async ({ reason }: z.infer<typeof formSchema>) =>
        await requestPulseAccess({ project_id: project.id, reason }),
      [project]
    ),
    onSuccess: async () => await refreshMyRequests(queryClient),
    throwOnError: true,
  });

  return (
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <DialogTrigger asChild>
        <Button
          className={cn("border-green-600 text-green-600", className)}
          type="button"
          variant="outline"
          disabled={!!pendingRequest}
        >
          {pendingRequest ? "Request Pending" : "Ask for pulse-level jobs"}
        </Button>
      </DialogTrigger>
      <DialogContent id="pulse-access-dialog">
        <DialogHeader>
          <DialogTitle>
            Allow pulse-level jobs on project {project.name}?
          </DialogTitle>
          <DialogDescription className="py-2">
            Pulse-level jobs play waveforms on the device's frames directly. The
            system admins decide.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((values) => {
              setDialogOpen(false);
              return pulseAccess.mutate(values);
            })}
          >
            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem className="grid gap-2">
                  <FormControl>
                    <Textarea
                      placeholder="Type your reason."
                      className="w-full my-2"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button
                type="submit"
                variant="outline"
                className="mx-auto w-full"
                disabled={!form.formState.isDirty}
              >
                Submit
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

interface Props {
  project: Project;
  className?: string;
  /** the user's requests, of which the pending pulse-access one on the project is shown */
  requests: UserRequest[];
}
