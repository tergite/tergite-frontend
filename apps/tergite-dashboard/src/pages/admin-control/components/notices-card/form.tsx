import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  Form,
} from "@/components/ui/form";
import { mergeDatetime } from "@/lib/utils";
import { DateTimeInput } from "@/components/ui/datetime-input";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DateTime, Duration } from "luxon";
import {
  apiBaseUrl,
  createNotice,
  refreshAllNoticeCounts,
  refreshAllNotices,
} from "@/lib/api-client";
import { NoticeSeverity } from "../../../../../types";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DurationInput } from "@/components/ui/duration-input";
import { Label } from "@/components/ui/label";
import { MultiInput } from "@/components/ui/multi-input";
import { ButtonGroup } from "@/components/ui/button-group";

const MAX_CHARS = 280;
const MIN_DURATION = Duration.fromObject({ minutes: 1 });
const MAX_DURATION = Duration.fromObject({ months: 3 });
const SEVERITY_OPTIONS = [
  NoticeSeverity.INFO,
  NoticeSeverity.WARNING,
  NoticeSeverity.CRITICAL,
] as const;

const formSchema = z.object({
  message: z.string().min(1).max(MAX_CHARS),
  severity: z.enum(SEVERITY_OPTIONS),
  target_user_emails: z.string().email().min(1).array().optional(),
  starts_at: z
    .object({
      date: z.date(),
      time: z.object({
        hour: z.number().int(),
        minute: z.number().int(),
        second: z.number().int(),
        millisecond: z.number().int().optional().default(0),
      }),
    })
    .transform(mergeDatetime)
    .refine((dt) => dt.isValid, { message: "invalid date" }),
  duration: z
    .object({
      hours: z.number().int(),
      minutes: z.number().int(),
      seconds: z.number().int(),
    })
    .transform(Duration.fromDurationLike)
    .refine((dt) => dt.isValid, { message: "invalid duration" })
    .refine((dt) => dt >= MIN_DURATION && dt <= MAX_DURATION, {
      message: `duration must be between ${MIN_DURATION.toISOTime()} and ${MAX_DURATION.toISOTime()}`,
    }),
});

type FormInput = z.input<typeof formSchema>;
type FormOutput = z.output<typeof formSchema>;

export default function NoticeForm() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const now = DateTime.now();
  const yesterday = now.minus({ day: 1 }).toJSDate();

  const creationForm = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      message: "",
      severity: NoticeSeverity.INFO,
      starts_at: {
        date: now.toJSDate(),
        time: now,
      },
      duration: {
        hours: 1,
        minutes: 0,
        seconds: 0,
      },
    },
  });

  const noticeCreation = useMutation({
    mutationKey: [apiBaseUrl, "admin", "notices", "post"],
    async mutationFn({
      duration,
      starts_at: startTimestamp,
      ...rest
    }: FormOutput) {
      const expires_at = startTimestamp.plus(duration).toISO()!;
      const starts_at = startTimestamp.toISO()!;
      return await createNotice(
        {
          expires_at,
          starts_at,
          ...rest,
        },
        { baseUrl: apiBaseUrl },
      );
    },
    async onSuccess(data) {
      await refreshAllNotices(queryClient);
      await refreshAllNoticeCounts(queryClient);
      const description = `Visible to ${data.target_user_ids?.length ?? "all"} users.`;
      toast({ title: "Notice posted", description });
    },
    throwOnError: true,
  });

  return (
    <Form {...creationForm}>
      <form
        onSubmit={creationForm.handleSubmit((values) =>
          noticeCreation.mutate(values),
        )}
        className="rounded-md border p-3 flex flex-col gap-3"
      >
        <p className="text-sm font-medium">New notice</p>
        <FormField
          control={creationForm.control}
          name="severity"
          render={({ field }) => (
            <FormItem>
              <FormControl>
                <Select
                  value={field.value}
                  name={field.name}
                  onValueChange={field.onChange}
                >
                  <SelectTrigger className="h-8 text-xs flex-1">
                    <SelectValue
                      onBlur={field.onBlur}
                      ref={field.ref}
                      placeholder="Severity"
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {SEVERITY_OPTIONS.map((s) => (
                      <SelectItem key={s} value={s} className="text-xs">
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormControl>
            </FormItem>
          )}
        />
        <FormField
          control={creationForm.control}
          name="message"
          render={({ field }) => (
            <FormItem className="flex flex-col gap-1">
              <FormLabel className="sr-only" htmlFor="notice-message">
                Message
              </FormLabel>
              <FormControl>
                <>
                  <Textarea
                    id="notice-message"
                    placeholder="Write a message..."
                    className="h-20 resize-none text-sm"
                    {...field}
                  />
                  <p
                    className={`text-xs self-end ${field.value.length >= MAX_CHARS ? "text-destructive" : "text-muted-foreground"}`}
                  >
                    {field.value.length}/{MAX_CHARS}
                  </p>
                </>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={creationForm.control}
          name="starts_at"
          render={({ field }) => (
            <FormItem>
              <ButtonGroup className="w-full">
                <Button
                  type="button"
                  variant="outline"
                  className="text-muted-foreground pointer-events-none"
                >
                  Starts
                </Button>

                <DateTimeInput
                  disabled={noticeCreation.isPending}
                  value={field.value}
                  onChange={field.onChange}
                  minDate={yesterday}
                />
              </ButtonGroup>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={creationForm.control}
          name="duration"
          render={({ field }) => (
            <FormItem>
              <FormControl>
                <div className="">
                  <Label className="text-muted-foreground" htmlFor="duration">
                    Duration
                  </Label>
                  <DurationInput id="duration" {...field} />
                </div>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={creationForm.control}
          name="target_user_emails"
          render={({ field }) => (
            <FormItem className="">
              <FormControl>
                <div className="flex flex-col">
                  <Label
                    className="text-muted-foreground mb-1"
                    htmlFor="user_emails"
                  >
                    Audience
                  </Label>
                  <MultiInput id="user_emails" type="email" {...field} />
                </div>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button
          type="submit"
          variant="default"
          size="sm"
          className="w-full"
          disabled={!creationForm.formState.isDirty}
        >
          Post
        </Button>
      </form>
    </Form>
  );
}
