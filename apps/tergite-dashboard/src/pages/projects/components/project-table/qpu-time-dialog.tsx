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
import {
  apiBaseUrl,
  refreshAllRequestsQueries,
  refreshMyProjectsQpuTimeRequestsQueries,
  requestQpuTimeExtension,
} from "@/lib/api-client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import {
  Project,
  QpuTimeExtensionPostBody,
  QpuTimeExtensionUserRequest,
  User,
} from "types";
import { z } from "zod";
import { Duration } from "luxon";
import { Textarea } from "@/components/ui/textarea";
import { cn, safeParseInt } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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

export function QpuTimeDialog(props: Props) {
  const { project, currentUser } = props;
  const isUserEditable = project.admin_id === currentUser?.id;
  const { className = "" } = props;
  return isUserEditable ? (
    <_QpuTimeDialog {...props} />
  ) : (
    <div className={className}>N/A</div>
  );
}

function _QpuTimeDialog({
  project,
  qpuTimeRequests,
  onSubmit = async () => {},
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
  const isRequestPending = useMemo(
    () =>
      qpuTimeRequests.filter(
        (v) => v.request.project_id === project.id && v.status === "pending"
      ).length > 0,
    [qpuTimeRequests, project]
  );

  const qpuExtension = useMutation({
    mutationKey: [
      apiBaseUrl,
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
        const response = await requestQpuTimeExtension(payload);
        refreshMyProjectsQpuTimeRequestsQueries(queryClient);
        refreshAllRequestsQueries(queryClient);
        return response;
      },
      [project, queryClient]
    ),
    onSuccess: onSubmit,
    throwOnError: true,
  });

  return (
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <DialogTrigger asChild>
        <Button
          className={cn("border-green-600 text-green-600", className)}
          type="button"
          variant="outline"
          disabled={isRequestPending}
        >
          {isRequestPending ? "Request Pending" : "More QPU time"}
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
                              field.onChange(safeParseInt(ev.target.value) ?? 0)
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
  currentUser: User;
  className?: string;
  qpuTimeRequests: QpuTimeExtensionUserRequest[];
  onSubmit?: (data: QpuTimeExtensionUserRequest) => Promise<void>;
}
