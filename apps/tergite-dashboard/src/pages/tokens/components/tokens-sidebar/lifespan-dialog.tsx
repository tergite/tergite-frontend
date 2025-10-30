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
  FormLabel,
} from "@/components/ui/form";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContentNoPortal,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  apiBaseUrl,
  refreshMyTokensQueries,
  updateAppToken,
} from "@/lib/api-client";
import { cn, mergeDatetime } from "@/lib/utils";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import {
  type AppToken,
  type AppTokenUpdateRequest,
  type ExtendedAppToken,
} from "types";
import { z } from "zod";
import { CalendarIcon } from "@radix-ui/react-icons";
import { TimeInput } from "@/components/ui/time-input";
import { DateTime } from "luxon";

const formSchema = z.object({
  expiration: z.object({
    date: z.date(),
    time: z.object({
      hour: z.number().int(),
      minute: z.number().int(),
      second: z.number().int(),
      millisecond: z.number().int().optional(),
    }),
  }),
});

export function TokenLifespanDialog({
  token,
  onEdit = async () => {},
  isDisabled,
}: Props) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const yesterday = DateTime.now().minus({ day: 1 }).toJSDate();
  const queryClient = useQueryClient();
  const editForm = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
  });

  const tokenEditing = useMutation({
    mutationKey: [apiBaseUrl, "me", "tokens", token.id, "put"],
    mutationFn: useCallback(
      async (values: z.infer<typeof formSchema>) => {
        const payload: AppTokenUpdateRequest = {
          expires_at: mergeDatetime(values.expiration).toISO() as string,
        };
        return await updateAppToken(token.id, payload);
      },
      [token.id]
    ),
    onSuccess: useCallback(
      async (data: AppToken) => {
        refreshMyTokensQueries(queryClient);
        return await onEdit(data);
      },
      [onEdit, queryClient]
    ),
    throwOnError: true,
  });

  useEffect(() => {
    editForm.reset({
      expiration: {
        date: token.expires_at.toJSDate(),
        time: token.expires_at,
      },
    });
  }, [editForm, token.expires_at]);

  return (
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <DialogTrigger asChild>
        <Button
          className="border-green-600 text-green-600"
          type="button"
          disabled={isDisabled}
          variant="outline"
        >
          Edit lifespan
        </Button>
      </DialogTrigger>
      <DialogContent id="edit-lifespan-dialog">
        <DialogHeader>
          <DialogTitle>Edit lifespan of token {token.title}?</DialogTitle>
          <DialogDescription className="py-5">
            Increase or decrease the time of expiry of the token.
          </DialogDescription>
        </DialogHeader>
        <Form {...editForm}>
          <form
            onSubmit={editForm.handleSubmit((values) => {
              setDialogOpen(false);
              return tokenEditing.mutate(values);
            })}
            className="grid gap-4 w-full"
          >
            <FormField
              control={editForm.control}
              name="expiration"
              render={({ field }) => (
                <FormItem className="grid gap-2">
                  <FormLabel>Expires at</FormLabel>
                  <Popover>
                    <PopoverTrigger asChild>
                      <FormControl>
                        <Button
                          id="datetime-input"
                          variant={"outline"}
                          disabled={tokenEditing.isPending}
                          className={cn(
                            "w-full pl-3 text-left font-normal",
                            !field.value?.date && "text-muted-foreground"
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
            <DialogFooter>
              <Button
                type="submit"
                variant="outline"
                className="mx-auto w-full"
                disabled={!editForm.formState.isDirty}
              >
                Save
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

interface Props {
  token: ExtendedAppToken;
  isDisabled: boolean;
  onEdit?: (data: AppToken) => Promise<void>;
}
