import { ChangeEvent, useCallback, forwardRef, useMemo } from "react";
import { Input } from "./input";
import { safeParseInt } from "@/lib/utils";

const DurationInput = forwardRef<HTMLInputElement, Props>(
  ({ value, onChange, ...props }, ref) => {
    const valueStr = useMemo(() => value && toLooseISOFormat(value), [value]);

    /**
     * Handles the event when the hours are changed
     */
    const handleHoursChange = useCallback(
      (ev: ChangeEvent<HTMLInputElement>) => {
        ev.preventDefault();
        const oldValue = value ?? { hours: 0, minutes: 0, seconds: 0 };
        const hours = safeParseInt(ev.target.value) ?? 0;
        return onChange && onChange({ ...oldValue, hours });
      },
      [onChange, value]
    );

    /**
     * Handles the event when the minutes are changed
     */
    const handleMinutesChange = useCallback(
      (ev: ChangeEvent<HTMLInputElement>) => {
        ev.preventDefault();
        const oldValue = value ?? { hours: 0, minutes: 0, seconds: 0 };
        const minutes = safeParseInt(ev.target.value) ?? 0;
        return onChange && onChange({ ...oldValue, minutes });
      },
      [onChange, value]
    );

    /**
     * Handles the event when the seconds are changed
     */
    const handleSecondsChange = useCallback(
      (ev: ChangeEvent<HTMLInputElement>) => {
        ev.preventDefault();
        const oldValue = value ?? { hours: 0, minutes: 0, seconds: 0 };
        const seconds = safeParseInt(ev.target.value) ?? 0;
        return onChange && onChange({ ...oldValue, seconds });
      },
      [onChange, value]
    );

    return (
      <>
        <div
          className="flex justify-between gap-2 items-baseline max-w-fit"
          {...props}
        >
          <Input
            id="duration-hours"
            type="number"
            min={0}
            placeholder="HH"
            value={value?.hours ?? undefined}
            onChange={handleHoursChange}
          />
          <span>:</span>
          <Input
            id="duration-minutes"
            type="number"
            min={0}
            max={59}
            placeholder="MM"
            value={value?.minutes ?? undefined}
            onChange={handleMinutesChange}
          />
          <span>:</span>
          <Input
            id="duration-seconds"
            type="number"
            min={0}
            max={59}
            placeholder="SS"
            value={value?.seconds ?? undefined}
            onChange={handleSecondsChange}
          />
        </div>

        <Input type="hidden" value={valueStr} ref={ref} readOnly {...props} />
      </>
    );
  }
);
Input.displayName = "DurationInput";

export { DurationInput };

interface Props
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    "value" | "onChange" | "type"
  > {
  value?: _DurationInfo;
  onChange?: (value?: _DurationInfo) => void;
}

interface _DurationInfo {
  hours: number;
  minutes: number;
  seconds: number;
}

/**
 * Converts a duration instance into a string of a loose ISO format (HH:mm:ss.SSS)
 *
 * It ignores the restriction that hours should be less than 23 hours
 *
 * @param value - the Duration instance
 * @returns - the ISO string representation of the value
 */
function toLooseISOFormat({ hours, minutes, seconds }: _DurationInfo): string {
  const paddedMinutes = `${minutes}`.padStart(2, "0");
  const paddedSeconds = `${seconds}`.padStart(2, "0");
  const paddedHours = `${hours}`.padStart(2, "0");

  return `${paddedHours}:${paddedMinutes}:${paddedSeconds}.000`;
}
