import { Button } from "@/components/ui/button";
import { DialogHeader, DialogFooter } from "@/components/ui/dialog";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  FormField,
  Form,
  FormControl,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import { refreshMyRequests, requestQpuTimeExtension } from "@/lib/api/requests";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import type { Project, UserRequest } from "@/lib/api/types";
import type { QpuTimeExtensionPostBody } from "@/lib/api/requests";
import { z } from "zod";
import { Duration } from "luxon";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { parseOptionalInt } from "@/lib/time";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

const formSchema = z.object({
  days: z.number().int().default(0),
  hours: z.number().int().default(0),
  minutes: z.number().int().default(0),
  seconds: z.number().int().default(0),
  reason: z.string().min(1),
});

const DURATION_FIELDS = [
  { name: "days", id: "days", label: "days" },
  { name: "hours", id: "hrs", label: "hrs" },
  { name: "minutes", id: "mins", label: "mins" },
  { name: "seconds", id: "secs", label: "secs" },
] as const;

export function QpuTimeRequestDialog({
  project,
  requests,
  className = "",
}: Props) {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const editForm = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      days: 0,
      hours: 0,
      minutes: 60,
      seconds: 0,
      reason: "",
    },
  });
  const pendingRequest = useMemo(
    () =>
      requests.find(
        (v) =>
          v.type === "project-qpu-seconds" &&
          v.resource_id === project.id &&
          v.status === "pending"
      ),
    [requests, project]
  );

  const qpuExtension = useMutation({
    mutationKey: [
      "me",
      "projects",
      project.id,
      "request-time-extension",
    ],
    mutationFn: useCallback(
      async (values: z.infer<typeof formSchema>) => {
        const { reason, ...extension } = values;
        const payload: QpuTimeExtensionPostBody = {
          seconds: Duration.fromObject(extension).as("seconds"),
          reason: reason,
          project_id: project.id,
        };
        return await requestQpuTimeExtension(payload);
      },
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
          {pendingRequest ? (
            <>
              Request Pending
              <Badge variant="outline" className="ml-2">
                {Duration.fromObject({
                  seconds: pendingRequest.metadata?.seconds,
                }).toHuman()}
              </Badge>
            </>
          ) : (
            "More QPU time"
          )}
        </Button>
      </DialogTrigger>
      <DialogContent id="qpu-time-dialog">
        <DialogHeader>
          <DialogTitle>
            Ask for more QPU time for project {project.name}?
          </DialogTitle>
          <DialogDescription className="py-2">More QPU time.</DialogDescription>
        </DialogHeader>
        <Form {...editForm}>
          <form
            onSubmit={editForm.handleSubmit((values) => {
              setDialogOpen(false);
              return qpuExtension.mutate(values);
            })}
            className=""
          >
            <div className="grid grid-cols-4 my-2">
              {DURATION_FIELDS.map(({ name, id, label }) => (
                <FormField
                  key={id}
                  control={editForm.control}
                  name={name}
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <div>
                          <Input
                            id={id}
                            type="number"
                            min={0}
                            {...field}
                            value={field.value}
                            onChange={(ev) =>
                              field.onChange(parseOptionalInt(ev.target.value) ?? 0)
                            }
                          />
                          <Label htmlFor={id}>{label}</Label>
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ))}
            </div>

            <FormField
              control={editForm.control}
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
                disabled={!editForm.formState.isDirty}
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
  /** the user's requests, of which the pending QPU-time one on the project is shown */
  requests: UserRequest[];
}
