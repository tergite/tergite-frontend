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
  InputDuration,
  User,
} from "types";
import { z } from "zod";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const formSchema = z.object({
  hours: z.number().int().default(0),
  days: z.number().int().default(0),
  minutes: z.number().int().default(0),
  seconds: z.number().int().default(0),
  milliseconds: z.number().int().default(0),
  reason: z.string().min(1),
});

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
      minutes: 60,
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
          seconds: toSeconds(extension),
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
              <FormField
                control={editForm.control}
                name="days"
                render={({ field }) => (
                  <FormItem className="">
                    <FormControl>
                      <div>
                        <Input
                          id="days"
                          type="number"
                          {...field}
                          onChange={(ev) =>
                            field.onChange(parseInt(ev.target.value))
                          }
                        />
                        <Label htmlFor="days">days</Label>
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={editForm.control}
                name="hours"
                render={({ field }) => (
                  <FormItem className="">
                    <FormControl>
                      <div>
                        <Input
                          id="hrs"
                          type="number"
                          {...field}
                          onChange={(ev) =>
                            field.onChange(parseInt(ev.target.value))
                          }
                        />
                        <Label htmlFor="hrs">hrs</Label>
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={editForm.control}
                name="minutes"
                render={({ field }) => (
                  <FormItem className="">
                    <FormControl>
                      <div>
                        <Input
                          id="mins"
                          type="number"
                          {...field}
                          onChange={(ev) =>
                            field.onChange(parseInt(ev.target.value))
                          }
                        />
                        <Label htmlFor="mins">mins</Label>
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={editForm.control}
                name="seconds"
                render={({ field }) => (
                  <FormItem className="">
                    <FormControl>
                      <div>
                        <Input
                          id="secs"
                          type="number"
                          {...field}
                          onChange={(ev) =>
                            field.onChange(parseInt(ev.target.value))
                          }
                        />
                        <Label htmlFor="secs">secs</Label>
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
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

/**
 * Converts a given value to seconds
 *
 * @param value - the value to convert to seconds
 */
function toSeconds({
  days = 0,
  hours = 0,
  milliseconds = 0,
  minutes = 0,
  seconds = 0,
}: InputDuration): number {
  return (
    seconds + minutes * 60 + milliseconds / 1000 + hours * 3_600 + days * 24
  );
}
