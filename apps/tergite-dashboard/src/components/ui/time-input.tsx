import { extractTime, formatTime } from "@/lib/time";
import { ChangeEvent, useCallback, useMemo } from "react";
import { Time } from "types";
import { Input } from "./input";

export function TimeInput({
  value,
  step = "1",
  onChange,
  onInput,
  ...props
}: Props) {
  const valueStr = useMemo(() => value && formatTime(value), [value]);
  const handleChangeEvent = useCallback(
    (ev: ChangeEvent<HTMLInputElement>) => {
      ev.preventDefault();
      return onChange && onChange(extractTime(ev.target.value || ""));
    },
    [onChange]
  );
  const handleInputEvent = useCallback(
    (ev: ChangeEvent<HTMLInputElement>) => {
      ev.preventDefault();
      onInput && onInput(extractTime(ev.target.value || ""));
    },
    [onInput]
  );

  return (
    <Input
      type="time"
      step={step}
      {...props}
      value={valueStr}
      onChange={handleChangeEvent}
      onInput={handleInputEvent}
    />
  );
}

interface Props
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    "value" | "onChange" | "onInput" | "type"
  > {
  value?: Time;
  onChange?: (value?: Time) => void;
  onInput?: (value?: Time) => void;
}
