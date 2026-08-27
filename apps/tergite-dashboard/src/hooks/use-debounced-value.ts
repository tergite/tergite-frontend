import { useEffect, useState } from "react";

/**
 * The given value, but only after it has stopped changing for `delayMs`.
 *
 * For inputs that drive a request: without this, a search endpoint sees one request per
 * keystroke.
 *
 * @param value - the value to settle
 * @param delayMs - how long the value must hold still
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return settled;
}
