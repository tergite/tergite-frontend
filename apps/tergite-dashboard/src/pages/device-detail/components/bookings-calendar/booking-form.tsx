import { cn, mergeDatetime } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookingsConfig, ErrorInfo, NewBookingInfo } from "types";
import { useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { refreshBookingsQueries } from "@/lib/api-client";
import { DateTime, Duration } from "luxon";
import { CalendarIcon } from "lucide-react";

import { Booking } from "types";
import {
  Popover,
  PopoverContentNoPortal,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { TimeInput } from "@/components/ui/time-input";
import { DurationInput } from "@/components/ui/duration-input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogClose,
  DialogFooter,
} from "@/components/ui/dialog";

export function BookingForm({
  className = "",
  dialogTitle,
  backend,
  initialBooking,
  onSuccess = () => {},
  onCancel = () => {},
  onError = () => {},
  bookingsConfig,
  defaultStartTimestamp,
  open,
  onOpenChange,
  mutate,
}: Props) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const now = DateTime.now();
  const yesterday = now.minus({ day: 1 }).toJSDate();
  const isEdit = !!initialBooking;
  const startUtc =
    initialBooking?.start_utc ?? defaultStartTimestamp ?? now.toISO();
  const initialStartTimestamp = DateTime.fromISO(startUtc);
  const initialEndTimestamp =
    initialBooking?.end_utc && DateTime.fromISO(initialBooking.end_utc);

  const minDuration = Duration.fromObject({
    seconds: bookingsConfig.min_time_slot_length,
  });
  const maxDuration = Duration.fromObject({
    seconds: bookingsConfig.max_time_slot_length,
  });
  const initialDuration = initialEndTimestamp
    ? initialEndTimestamp.diff(initialStartTimestamp)
    : minDuration;
  // TODO: Limit the possibility of creating a new slot for a given day
  //    if slots for that day are maxed out
  // const maxSlotsPerDay = bookingsConfig.max_slots_per_day;

  const formSchema = useMemo(
    () =>
      z.object({
        startDate: z
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
          .refine((dt) => dt >= now, {
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
          .refine((dt) => dt >= minDuration && dt <= maxDuration, {
            message: `duration must be between ${minDuration.toISOTime()} and ${maxDuration.toISOTime()}`,
          }),
      }),
    [maxDuration, minDuration, now]
  );
  type FormInput = z.input<typeof formSchema>;
  type FormOutput = z.output<typeof formSchema>;

  const formObj = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(formSchema),
    values: {
      startDate: {
        date: initialStartTimestamp.toJSDate(),
        time: initialStartTimestamp,
      },
      duration: {
        hours: 0,
        minutes: 0,
        seconds: initialDuration.as("seconds"),
      },
    },
  });

  const handleCancel = useCallback(async () => {
    formObj.reset();
    onCancel();
  }, [formObj, onCancel]);

  const handleOpenChange = useCallback(
    async (value: boolean) => {
      if (!value) {
        formObj.reset();
      }
      onOpenChange(value);
    },
    [formObj, onOpenChange]
  );

  const bookingUpdate = useMutation({
    mutationFn: useCallback(
      async ({ startDate, duration }: FormOutput) => {
        const start_utc = startDate.toUTC().toISO();
        if (start_utc == null) {
          throw new Error("invalid start date");
        }

        const durationObj = Duration.fromDurationLike(duration);
        if (durationObj < minDuration) {
          throw new Error(
            `duration is less than minimum ${minDuration.toHuman()}`
          );
        } else if (durationObj > maxDuration) {
          throw new Error(
            `duration is more than maximum ${maxDuration.toHuman()}`
          );
        }

        const end_utc = startDate.plus(duration).toUTC().toISO();
        if (end_utc == null) {
          throw new Error("invalid duration");
        }

        return await mutate(backend, { start_utc, end_utc }, initialBooking);
      },
      [backend, minDuration, maxDuration, initialBooking, mutate]
    ),
    onSuccess: useCallback(
      async (booking: Booking) => {
        await refreshBookingsQueries(queryClient, backend);
        const startTime = DateTime.fromISO(booking.start_utc).toLocaleString(
          DateTime.DATETIME_SHORT
        );
        toast({ description: `Booking at ${startTime} saved` });
        onSuccess(booking);
        handleOpenChange(false);
      },
      [backend, queryClient, handleOpenChange, onSuccess, toast]
    ),
    onError,
  });

  // // A hack: for some reason formObj.formState.isDirty was not always right especially
  const isFormDirty = Object.keys(formObj.formState.dirtyFields).length;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent id="booking-form-dialog">
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
          <DialogDescription className="py-5">
            Book a time slot on {backend} to avoid being interrupted by other
            users.
          </DialogDescription>
        </DialogHeader>
        <Form {...formObj}>
          <form
            data-cy-booking-form
            onSubmit={formObj.handleSubmit((values) =>
              bookingUpdate.mutate(values)
            )}
            onReset={handleCancel}
            className={cn("grid gap-4 w-full", className)}
          >
            <FormField
              control={formObj.control}
              name="startDate"
              render={({ field }) => (
                <FormItem className="grid gap-2">
                  <FormLabel>Starts</FormLabel>
                  <Popover>
                    <PopoverTrigger asChild>
                      <FormControl>
                        <Button
                          id="datetime-input"
                          variant={"outline"}
                          disabled={bookingUpdate.isPending}
                          className={cn(
                            "w-full pl-3 text-left font-normal",
                            !field.value && "text-muted-foreground"
                          )}
                        >
                          {field.value?.date ? (
                            mergeDatetime(field.value)
                              .setLocale("en-gb")
                              .toLocaleString(
                                DateTime.DATETIME_MED_WITH_SECONDS
                              )
                          ) : (
                            <span>Pick a date and time</span>
                          )}
                          <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                        </Button>
                      </FormControl>
                    </PopoverTrigger>
                    <PopoverContentNoPortal
                      className="w-auto p-0"
                      align="start"
                    >
                      <Calendar
                        mode="single"
                        selected={field.value?.date as Date}
                        onSelect={(date) =>
                          field.onChange({ date, time: field.value?.time })
                        }
                        disabled={(date) => date < yesterday}
                        initialFocus
                      />
                      <TimeInput
                        className="w-max py-6 mx-auto my-3"
                        value={field.value?.time}
                        onChange={(time) =>
                          field.onChange({ time, date: field.value?.date })
                        }
                      />
                    </PopoverContentNoPortal>
                  </Popover>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={formObj.control}
              name="duration"
              render={({ field }) => (
                <FormItem className="">
                  <FormControl>
                    <div className="">
                      <Label className="text-muted-foreground" htmlFor="name">
                        Duration
                      </Label>
                      <DurationInput id="duration" {...field} />
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button
                disabled={bookingUpdate.isPending || (isEdit && !isFormDirty)}
                type="submit"
                variant="default"
              >
                Save
              </Button>

              <DialogClose asChild>
                <Button
                  type="reset"
                  disabled={bookingUpdate.isPending}
                  variant="secondary"
                  className="border"
                >
                  Cancel
                </Button>
              </DialogClose>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

interface Props {
  className?: string;
  dialogTitle: string;
  backend: string;
  initialBooking?: Booking;
  defaultStartTimestamp?: string;
  onSuccess?: (booking: Booking) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  bookingsConfig: BookingsConfig;
  onCancel?: () => void;
  onError?: (err: ErrorInfo | Error) => void;
  mutate: (
    backend: string,
    newInfo: NewBookingInfo,
    original?: Booking
  ) => Promise<Booking>;
}
