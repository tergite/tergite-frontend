import { Button } from "@/components/ui/button";
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
import { grantQpuSeconds, refreshAllAdminQueries } from "@/lib/api-client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  ErrorInfo,
  GrantTarget,
  type QpuSecondsGrantReport,
} from "../../../../types";

const formSchema = z
  .object({
    seconds: z.coerce.number().positive("must be more than zero"),
    target: z.nativeEnum(GrantTarget),
    target_emails: z.string().email().array().default([]),
    reason: z.string().min(1, "required"),
  })
  .refine(
    (value) =>
      value.target !== GrantTarget.EMAILS || value.target_emails.length > 0,
    { message: "at least one email is required", path: ["target_emails"] },
  );

export function GrantQpuSecondsForm({ onClose, className = "" }: Props) {
  const queryClient = useQueryClient();
  const [report, setReport] = useState<QpuSecondsGrantReport>();
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
  const isAllPersonal = target === GrantTarget.ALL_PERSONAL;

  const submit = useCallback(
    async (values: z.infer<typeof formSchema>) => {
      try {
        const result = await grantQpuSeconds(
          {
            seconds: values.seconds,
            target: values.target,
            reason: values.reason,
            target_emails: isAllPersonal ? undefined : values.target_emails,
          },
          // a fresh key per submission: a retry of *this* click must not double-grant,
          // but a deliberate second grant should be its own operation
          crypto.randomUUID(),
        );
        setReport(result);
        await refreshAllAdminQueries(queryClient);
      } catch (error) {
        const message = (error as ErrorInfo)?.message ?? String(error);
        grantForm.setError("seconds", { type: "custom", message });
      }
    },
    [grantForm, isAllPersonal, queryClient],
  );

  return (
    <Card id="grant-qpu-seconds" className={className}>
      <CardHeader className="flex flex-row items-center justify-between bg-muted/50">
        <CardTitle className="text-lg">Grant QPU time</CardTitle>
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
      </CardHeader>
      <Form {...grantForm}>
        <form onSubmit={grantForm.handleSubmit(submit)}>
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
                        <SelectItem value={GrantTarget.ALL_PERSONAL}>
                          All personal projects
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {!isAllPersonal && (
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

            {report && (
              <div data-cy-grant-report className="grid gap-1 border-t pt-3">
                <span className="font-medium">
                  {report.granted} project{report.granted === 1 ? "" : "s"}{" "}
                  granted {report.seconds}s
                </span>
                {report.skipped.length > 0 && (
                  <>
                    <span className="text-muted-foreground">
                      {report.skipped.length} skipped
                    </span>
                    <ul className="grid gap-1">
                      {report.skipped.map((item) => (
                        <li key={item.email} className="text-muted-foreground">
                          {item.email}: {item.why}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}
          </CardContent>
          <CardFooter className="border-t bg-muted/50 px-6 py-3">
            {isAllPersonal ? (
              // irreversible and wide-reaching, so it gets a confirmation step
              <ConfirmDialog
                title="Grant to every personal project?"
                description="This adds QPU time to all personal projects and cannot be undone."
                onConfirm={grantForm.handleSubmit(submit)}
                trigger={
                  <Button
                    type="button"
                    data-cy-grant-submit
                    className="w-full"
                    disabled={grantForm.formState.isSubmitting}
                  >
                    Grant to all
                  </Button>
                }
              />
            ) : (
              <Button
                type="submit"
                data-cy-grant-submit
                className="w-full"
                disabled={grantForm.formState.isSubmitting}
              >
                Grant
              </Button>
            )}
          </CardFooter>
        </form>
      </Form>
    </Card>
  );
}

interface Props {
  onClose: () => void;
  className?: string;
}
