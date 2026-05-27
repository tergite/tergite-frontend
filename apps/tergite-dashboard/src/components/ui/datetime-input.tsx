import { cn, mergeDatetime } from "@/lib/utils";
import { CalendarIcon } from "lucide-react";
import { DateTime } from "luxon";
import { FormControl } from "./form";
import { PopoverContentNoPortal, Popover, PopoverTrigger } from "./popover";
import { TimeInput } from "./time-input";
import { Button } from "./button";
import { Time } from "types";
import { Calendar } from "./calendar";
import { Label } from "./label";

export function DateTimeInput({
  disabled,
  onChange,
  value,
  minDate,
  label,
}: Props) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <FormControl>
          <>
            {label && (
              <Label className="text-muted-foreground" htmlFor="datetime-input">
                {label}
              </Label>
            )}
            <Button
              id="datetime-input"
              variant={"outline"}
              disabled={disabled}
              className={cn(
                "w-full pl-3 text-left font-normal",
                !value && "text-muted-foreground",
              )}
            >
              {value?.date ? (
                mergeDatetime(value)
                  .setLocale("en-gb")
                  .toLocaleString(DateTime.DATETIME_MED_WITH_SECONDS)
              ) : (
                <span>Pick a date and time</span>
              )}
              <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
            </Button>
          </>
        </FormControl>
      </PopoverTrigger>
      <PopoverContentNoPortal className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={value?.date as Date}
          onSelect={(date) => onChange({ date, time: value?.time })}
          disabled={(date) => date < minDate}
          initialFocus
        />
        <TimeInput
          className="w-max py-6 mx-auto my-3"
          value={value?.time}
          onChange={(time) => onChange({ time, date: value?.date })}
        />
      </PopoverContentNoPortal>
    </Popover>
  );
}

interface _ValueType {
  date?: Date;
  time?: Time | DateTime;
}

interface Props {
  value?: _ValueType;
  onChange: (value: _ValueType) => void;
  label?: string;
  disabled: boolean;
  minDate: Date;
}
