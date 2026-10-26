import { ComboboxInput } from "@/components/ui/combobox-input";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { getUserEmailsQuery } from "@/lib/api/projects";
import { useQuery } from "@tanstack/react-query";
import * as React from "react";

const SEARCH_DELAY_MS = 300;

/**
 * An email input that suggests addresses already known to MSS.
 *
 * Doubles as the row control for the member list, so it takes exactly the props a plain
 * input does and fetches its own suggestions.
 *
 * The search runs server-side because the endpoint answers a page at a time, so
 * filtering only what the first page happened to contain would hide the rest. It is
 * debounced so that a request follows a pause in typing rather than every keystroke,
 * and react-query caches each term, so going back over one costs nothing.
 */
export function UserEmailInput(
  props: React.InputHTMLAttributes<HTMLInputElement>
) {
  const search = useDebouncedValue(`${props.value ?? ""}`, SEARCH_DELAY_MS);
  const { data: emails = [] } = useQuery(getUserEmailsQuery({ search }));

  return <ComboboxInput {...props} suggestions={emails} />;
}
