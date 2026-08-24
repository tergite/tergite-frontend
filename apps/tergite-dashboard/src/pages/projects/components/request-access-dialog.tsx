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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  refreshMyProjectsQueries,
  refreshMyRequests,
  requestProjectAccess,
} from "@/lib/api-client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";
import { ErrorInfo } from "types";
import { z } from "zod";
import { toast } from "@/hooks/use-toast";

const formSchema = z.object({
  project_ext_id: z.string().min(1, "required"),
  reason: z.string().min(1, "required"),
});

export function RequestAccessDialog() {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const requestForm = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { project_ext_id: "", reason: "" },
  });

  const accessRequest = useMutation({
    mutationFn: useCallback(
      (values: z.infer<typeof formSchema>) => requestProjectAccess(values),
      [],
    ),
    onSuccess: useCallback(async () => {
      await refreshMyRequests(queryClient);
      await refreshMyProjectsQueries(queryClient);
      toast({
        title: "Access requested",
        description: "The project's admin decides next.",
      });
      requestForm.reset();
      setIsOpen(false);
    }, [queryClient, requestForm]),
    onError: useCallback(
      (error: ErrorInfo | Error) => {
        // a 404 means no such project, which is the common case of a mistyped ID;
        // surface it on the field so the user can correct it themselves
        const field =
          (error as ErrorInfo)?.status === 404 ? "project_ext_id" : "reason";
        requestForm.setError(field, {
          type: "custom",
          message: error?.message ?? String(error),
        });
      },
      [requestForm],
    ),
  });

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button type="button" data-cy-request-access>
          Request access
        </Button>
      </DialogTrigger>
      <DialogContent id="request-access-dialog">
        <DialogHeader>
          <DialogTitle>Request access to a project</DialogTitle>
          <DialogDescription className="py-2">
            Enter the external ID of a project you already know about. Its admin
            decides.
          </DialogDescription>
        </DialogHeader>
        <Form {...requestForm}>
          <form
            onSubmit={requestForm.handleSubmit((values) =>
              accessRequest.mutate(values),
            )}
          >
            <FormField
              control={requestForm.control}
              name="project_ext_id"
              render={({ field }) => (
                <FormItem className="grid gap-2 my-2">
                  <Label htmlFor="project_ext_id">Project External ID</Label>
                  <FormControl>
                    <Input id="project_ext_id" type="text" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={requestForm.control}
              name="reason"
              render={({ field }) => (
                <FormItem className="grid gap-2 my-2">
                  <Label htmlFor="reason">Reason</Label>
                  <FormControl>
                    <Textarea
                      id="reason"
                      placeholder="Why do you need access?"
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
                disabled={accessRequest.isPending}
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
