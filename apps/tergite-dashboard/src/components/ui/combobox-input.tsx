import * as React from "react";
import { Input } from "./input";
import { Popover, PopoverAnchor, PopoverContentNoPortal } from "./popover";
import { cn } from "@/lib/utils";

const MAX_SUGGESTIONS = 8;

/**
 * A free-text input that offers matching suggestions beneath it.
 *
 * Not a `<datalist>`: Firefox and iOS Safari render that only partially, and the usual
 * feature test passes on exactly those browsers, so a fallback could not be triggered
 * where it is needed. Not a closed list either — the value the caller types wins, which
 * matters where an address may belong to someone who has never logged in.
 */
const ComboboxInput = React.forwardRef<HTMLInputElement, Props>(
  (
    { suggestions = [], value, onChange, onKeyDown, className, ...props },
    ref
  ) => {
    const [isOpen, setIsOpen] = React.useState(false);
    const [activeIndex, setActiveIndex] = React.useState(-1);

    const matches = React.useMemo(() => {
      const query = `${value ?? ""}`.trim().toLowerCase();
      return suggestions
        .filter((item) => !query || item.toLowerCase().includes(query))
        .slice(0, MAX_SUGGESTIONS);
    }, [suggestions, value]);

    const pick = React.useCallback(
      (item: string) => {
        // the only part a change handler reads, and all react-hook-form wants; a real
        // ChangeEvent cannot be built for something the user never typed
        onChange?.({
          target: { name: props.name, value: item },
        } as React.ChangeEvent<HTMLInputElement>);
        setIsOpen(false);
        setActiveIndex(-1);
      },
      [onChange, props.name]
    );

    const handleKeyDown = React.useCallback(
      (ev: React.KeyboardEvent<HTMLInputElement>) => {
        onKeyDown?.(ev);
        if (!isOpen || matches.length === 0) {
          return;
        }
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
          ev.preventDefault();
          const step = ev.key === "ArrowDown" ? 1 : -1;
          setActiveIndex(
            (prev) => (prev + step + matches.length) % matches.length
          );
        } else if (ev.key === "Enter" && activeIndex >= 0) {
          // only when one is highlighted, so Enter still submits the form otherwise
          ev.preventDefault();
          pick(matches[activeIndex]);
        } else if (ev.key === "Escape") {
          setIsOpen(false);
        }
      },
      [activeIndex, isOpen, matches, onKeyDown, pick]
    );

    return (
      <Popover open={isOpen && matches.length > 0} onOpenChange={setIsOpen}>
        <PopoverAnchor asChild>
          <Input
            ref={ref}
            value={value}
            className={className}
            role="combobox"
            aria-expanded={isOpen && matches.length > 0}
            autoComplete="off"
            onChange={(ev) => {
              setIsOpen(true);
              setActiveIndex(-1);
              onChange?.(ev);
            }}
            onFocus={() => setIsOpen(true)}
            onKeyDown={handleKeyDown}
            {...props}
          />
        </PopoverAnchor>
        <PopoverContentNoPortal
          align="start"
          className="w-[--radix-popover-trigger-width] min-w-56 p-1"
          // the input keeps focus, or typing would end the moment the list opened
          onOpenAutoFocus={(ev) => ev.preventDefault()}
          onCloseAutoFocus={(ev) => ev.preventDefault()}
        >
          <ul data-cy-suggestions role="listbox" className="grid">
            {matches.map((item, index) => (
              <li key={item}>
                <button
                  type="button"
                  role="option"
                  aria-selected={index === activeIndex}
                  className={cn(
                    "w-full rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent",
                    index === activeIndex && "bg-accent"
                  )}
                  // mousedown, not click: blur would close the list first
                  onMouseDown={(ev) => {
                    ev.preventDefault();
                    pick(item);
                  }}
                >
                  {item}
                </button>
              </li>
            ))}
          </ul>
        </PopoverContentNoPortal>
      </Popover>
    );
  }
);
ComboboxInput.displayName = "ComboboxInput";

interface Props extends React.InputHTMLAttributes<HTMLInputElement> {
  suggestions?: string[];
}

export { ComboboxInput };
