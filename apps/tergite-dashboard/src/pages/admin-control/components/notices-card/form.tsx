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
import { mergeDatetime, SEVERITY_LABELS } from "@/lib/utils";
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

const MAX_CHARS = 280;
const MIN_DURATION = Duration.fromObject({ minutes: 1 });
const MAX_DURATION = Duration.fromObject({ months: 3 });

const formSchema = z.object({
  message: z.string().min(1).max(MAX_CHARS),
  severity: z.nativeEnum(NoticeSeverity),
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
    .refine((dt) => dt.isValid, { message: "invalid date" })
    .refine((dt) => dt >= DateTime.now(), {
      message: "date must be in future",
    }),
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
          name="message"
          render={({ field }) => (
            <FormItem className="flex flex-col gap-1.5">
              <FormLabel className="sr-only">Message</FormLabel>
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
          name="severity"
          render={({ field }) => (
            <FormItem>
              <FormControl>
                <Select {...field}>
                  <SelectTrigger className="h-8 text-xs flex-1">
                    <SelectValue placeholder="Severity" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.values(NoticeSeverity).map((s) => (
                      <SelectItem key={s} value={s} className="text-xs">
                        {SEVERITY_LABELS[s]}
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
          name="starts_at"
          render={({ field }) => (
            <FormItem className="grid gap-2">
              <DateTimeInput
                disabled={noticeCreation.isPending}
                value={field.value}
                onChange={field.onChange}
                minDate={yesterday}
                label="Starts"
              />
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={creationForm.control}
          name="duration"
          render={({ field }) => (
            <FormItem className="">
              <FormControl>
                <div className="">
                  <Label className="text-muted-foreground" htmlFor="duration">
                    Duration (HH:mm:ss)
                  </Label>
                  <DurationInput id="duration" {...field} />
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
