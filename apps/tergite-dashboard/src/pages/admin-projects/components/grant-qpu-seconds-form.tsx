import { Button, IconButton } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MultiInput } from "@/components/ui/multi-input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { grantQpuSeconds } from "@/lib/api-client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  GrantTarget,
  QpuSecondsGrantPostBody,
  type QpuSecondsGrantReport,
} from "../../../../types";
import { toast } from "@/hooks/use-toast";
import { X } from "lucide-react";

const formSchema = z
  .object({
    seconds: z.coerce.number().positive("must be more than zero"),
    target: z.nativeEnum(GrantTarget),
    target_emails: z.optional(z.string().email().array()),
    reason: z.string().min(1, "required"),
  })
  .refine(
    (value) =>
      value.target !== GrantTarget.EMAILS || value.target_emails?.length,
    { message: "at least one email is required", path: ["target_emails"] }
  );

export function GrantQpuSecondsForm({
  onClose,
  className = "",
  grantReport,
  idempotencyKey,
  onGrant,
  onCancel = () => {},
}: Props) {
  const [requestBody, setRequestBody] =
    useState<QpuSecondsGrantPostBody | null>(null);
  const grantForm = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      seconds: 3600,
      target: GrantTarget.EMAILS,
      target_emails: [],
      reason: "",
    },
  });
  const target = grantForm.watch("target");
  const isGrantingAllPersonalProjects =
    target === GrantTarget.ALL_PERSONAL_PROJECTS;

  const qpuSecondsGrant = useMutation({
    mutationFn: async (values: z.infer<typeof formSchema>) => {
      return await grantQpuSeconds(values, idempotencyKey);
    },
    onSuccess: useCallback(
      async (report: QpuSecondsGrantReport) => {
        await onGrant(report);
        toast({ description: `QPU seconds granted` });
        grantForm.reset();
      },
      [onGrant, grantForm]
    ),
    throwOnError: true,
  });

  const handleConfirm = useCallback(() => {
    if (!requestBody) return;
    qpuSecondsGrant.mutate(requestBody!);
  }, [requestBody, qpuSecondsGrant]);

  const handleCancel = useCallback(() => {
    grantForm.reset();
    setRequestBody(null);
    onCancel();
  }, [grantForm, setRequestBody, onCancel]);

  const handleDialogCancel = useCallback(() => {
    setRequestBody(null);
  }, [setRequestBody]);

  // A hack: for some reason editForm.formState.isDirty was not always right especially
  //   when one clicked on another project when they had just editted only the user_emails field but not submitted
  //   if the new project had everything in common with the project, except say the user_emails, editForm.formState.isDirty
  //   would still show that it is dirty yet it should reset whenever new values are passed to it during initialization
  const isFormDirty = Object.keys(grantForm.formState.dirtyFields).length;

  return (
    <Card id="grant-qpu-seconds" className={className}>
      <CardHeader className="flex flex-row items-center bg-muted/50 justify-between space-y-0">
        <div className="grid gap-0.5">
          <CardTitle className="group flex items-center gap-2 text-lg">
            Grant QPU seconds
          </CardTitle>
        </div>
        <IconButton Icon={X} variant="ghost" onClick={onClose} />
      </CardHeader>
      <Form {...grantForm}>
        <form
          onSubmit={grantForm.handleSubmit(setRequestBody)}
          onReset={handleCancel}
        >
          <CardContent className="p-6 text-sm grid gap-4">
            <FormField
              control={grantForm.control}
              name="seconds"
              render={({ field }) => (
                <FormItem className="grid gap-2">
                  <Label htmlFor="grant-seconds">Seconds</Label>
                  <FormControl>
                    <Input id="grant-seconds" type="number" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={grantForm.control}
              name="target"
              render={({ field }) => (
                <FormItem className="grid gap-2">
                  <Label htmlFor="grant-target">Apply to</Label>
                  <FormControl>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                      name={field.name}
                    >
                      <SelectTrigger id="grant-target">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent data-cy-grant-target-select>
                        <SelectItem value={GrantTarget.EMAILS}>
                          These users
                        </SelectItem>
                        <SelectItem value={GrantTarget.ALL_PERSONAL_PROJECTS}>
                          All personal projects
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {!isGrantingAllPersonalProjects && (
              <FormField
                control={grantForm.control}
                name="target_emails"
                render={({ field }) => (
                  <FormItem className="grid gap-2">
                    <Label htmlFor="grant-emails">User emails</Label>
                    <FormControl>
                      <div id="grant-emails-wrapper">
                        <MultiInput id="grant-emails" type="email" {...field} />
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <FormField
              control={grantForm.control}
              name="reason"
              render={({ field }) => (
                <FormItem className="grid gap-2">
                  <Label htmlFor="grant-reason">Reason</Label>
                  <FormControl>
                    <Textarea
                      id="grant-reason"
                      placeholder="Why is this being granted?"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Probably move this to its own private component */}
            {grantReport && (
              <div data-cy-grant-report className="grid gap-1 border-t pt-3">
                <span className="font-medium">
                  {grantReport.granted} project
                  {grantReport.granted === 1 ? "" : "s"} granted{" "}
                  {grantReport.seconds}s
                </span>
                {
                  /* FIXME: All the more reason to have a separate component. This needs to be scrollable as the number of skipped items might be high*/
                  grantReport.skipped.length > 0 && (
                    <>
                      <span className="text-muted-foreground">
                        {grantReport.skipped.length} skipped
                      </span>
                      <ul className="grid gap-1">
                        {grantReport.skipped.map((item) => (
                          <li
                            key={item.email}
                            className="text-muted-foreground"
                          >
                            {item.email}: {item.why}
                          </li>
                        ))}
                      </ul>
                    </>
                  )
                }
              </div>
            )}
          </CardContent>
          <CardFooter className="grid grid-cols-2 gap-2 border-t bg-muted/50 px-6 py-3">
            <ConfirmDialog
              title="Grant to multiple personal projects?"
              description="This adds QPU time to the selected personal projects and cannot be undone."
              onConfirm={handleConfirm}
              onCancel={handleDialogCancel}
              onClose={handleDialogCancel}
              trigger={
                <Button
                  type="submit"
                  data-cy-grant-submit
                  variant="default"
                  disabled={
                    !!requestBody || qpuSecondsGrant.isPending || !isFormDirty
                  }
                >
                  Grant
                </Button>
              }
            />

            <Button
              type="reset"
              disabled={qpuSecondsGrant.isPending}
              variant="secondary"
              className="border"
            >
              Cancel
            </Button>
          </CardFooter>
        </form>
      </Form>
    </Card>
  );
}

interface Props {
  onClose: () => void;
  grantReport?: QpuSecondsGrantReport;
  idempotencyKey: string;
  onGrant: (report: QpuSecondsGrantReport) => Promise<void>;
  onCancel?: () => void;
  className?: string;
}
