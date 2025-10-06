import { ChangeEvent, useCallback, useMemo, forwardRef } from "react";
import { Input } from "./input";
import { Duration } from "luxon";

const DurationInput = forwardRef<HTMLInputElement, Props>(
  ({ value, step = "1", onChange, onInput, ...props }, ref) => {
    const valueStr = useMemo(
      () => value && Duration.fromDurationLike(value).toISOTime(),
      [value]
    );
    const handleChangeEvent = useCallback(
      (ev: ChangeEvent<HTMLInputElement>) => {
        ev.preventDefault();
        return (
          onChange && onChange(Duration.fromISOTime(ev.target.value || ""))
        );
      },
      [onChange]
    );
    const handleInputEvent = useCallback(
      (ev: ChangeEvent<HTMLInputElement>) => {
        ev.preventDefault();
        onInput && onInput(Duration.fromISOTime(ev.target.value || ""));
      },
      [onInput]
    );

    return (
      <Input
        type="time"
        step={step}
        {...props}
        value={valueStr ?? undefined}
        onChange={handleChangeEvent}
        onInput={handleInputEvent}
        ref={ref}
      />
    );
  }
);
Input.displayName = "DurationInput";

export { DurationInput };

interface Props
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    "value" | "onChange" | "onInput" | "type"
  > {
  value?: _DurationInfo;
  onChange?: (value?: _DurationInfo) => void;
  onInput?: (value?: _DurationInfo) => void;
}

interface _DurationInfo {
  hours: number;
  minutes: number;
  seconds: number;
}
