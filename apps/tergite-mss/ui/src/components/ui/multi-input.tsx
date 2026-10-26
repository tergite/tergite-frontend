import {
  ChangeEvent,
  HTMLInputTypeAttribute,
  MouseEvent,
  useCallback,
  useMemo,
  useState,
} from "react";
import { Input } from "./input";
import { IconButton } from "./button";
import { Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import React from "react";

const MultiInput = React.forwardRef<HTMLInputElement, Props>(
  ({ value, type, name, onChange, InputComponent, ...props }, ref) => {
    const [stringValue, setStringValue] = useState(toStringValue(value));
    const handleOnChange = useCallback(() => {
      const inputValue = toinputValue(type, stringValue);
      onChange && onChange(inputValue);
    }, [onChange, stringValue, type]);

    const handleMultiInputChange = useCallback(
      (v: InputValue | undefined) => {
        setStringValue(toStringValue(v));
        onChange && onChange(v);
      },
      [setStringValue, onChange]
    );

    return (
      <>
        <input
          name={name}
          value={stringValue}
          onChange={handleOnChange}
          type="text"
          {...props}
          ref={ref}
          className="h-0 w-0"
        />
        <_MultiInput
          {...props}
          type={type}
          value={value}
          onChange={handleMultiInputChange}
          InputComponent={InputComponent}
        />
      </>
    );
  }
);
MultiInput.displayName = "MultiInput";

function _MultiInput({
  id,
  value,
  type,
  disabled,
  onChange,
  className = "",
  InputComponent = Input,
  ...rest
}: Props) {
  const defaultValue = useMemo(() => (type == "number" ? [0] : [""]), [type]);

  const handleAddBtnClick = useCallback(
    (ev: MouseEvent<HTMLButtonElement>) => {
      ev.preventDefault();
      const newValue = [...(value || []), defaultValue[0]];
      onChange && onChange(newValue);
    },
    [onChange, defaultValue, value]
  );

  const handleCloseBtnClick = useCallback(
    (index: number) => {
      const newValue = value?.filter((_v, i) => index !== i);
      onChange && onChange(newValue);
    },
    [value, onChange]
  );

  const handleInputChange = useCallback(
    (index: number) => (ev: ChangeEvent<HTMLInputElement>) => {
      const newValue = ev.target.value;
      const newInnerValue = value?.map((v, i) => (i === index ? newValue : v));
      onChange && onChange(newInnerValue);
    },
    [value, onChange]
  );

  return (
    <>
      {value &&
        value.map((item, index) => (
          <div
            id={`${id}-${index}-wrapper`}
            data-cy-input-wrapper={item}
            aria-disabled={disabled}
            key={index}
            className={cn("w-full grid grid-cols-9", className)}
          >
            <InputComponent
              id={`${id}-${index}`}
              disabled={disabled}
              value={item}
              type={type}
              data-cy-inner-input={index}
              data-index={index}
              className="rounded-l-md rounded-r-none col-span-8"
              onChange={handleInputChange(index)}
              {...rest}
            />
            <IconButton
              id={`${id}-${index}-del-btn`}
              disabled={disabled}
              variant="outline"
              className="rounded-l-none focus:mr-[1px] disabled:text-muted-foreground disabled:bg-muted col-span-1"
              data-cy-multi-input-close-btn={index}
              Icon={X}
              type="button"
              onClick={() => handleCloseBtnClick(index)}
            />
          </div>
        ))}
      <IconButton
        id={`${id}-add-btn`}
        type="button"
        variant="outline"
        className="disabled:text-muted-foreground disabled:bg-muted"
        data-cy-multi-input-add-btn
        Icon={Plus}
        onClick={handleAddBtnClick}
        disabled={disabled}
      />
    </>
  );
}

/**
 * Converts the input value to a string
 *
 * @param value - the value in the form of InputValue
 * @returns - the string form of the input value
 */
function toStringValue(value: InputValue | undefined): string | undefined {
  return value?.map((v) => `${v}`).join(",");
}

/**
 * Converts the value to an instance of InputValue
 *
 * @param type - the type of the input
 * @param value - the value in the form of a string
 * @returns - the InputValue form of the input value
 */
function toinputValue(
  type: HTMLInputTypeAttribute | undefined,
  value: string | undefined
): InputValue | undefined {
  const substrings = value?.split("");
  if (type === "number") {
    return substrings?.map((v) => parseFloat(v));
  }
  return substrings;
}

type InputValue = (string | number)[];

interface Props
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    "value" | "onChange"
  > {
  value?: InputValue;
  onChange?: (value?: InputValue) => void;
  // swap in a richer control per row, e.g. one that suggests as you type
  InputComponent?: React.ComponentType<
    React.InputHTMLAttributes<HTMLInputElement>
  >;
}

export { MultiInput };
