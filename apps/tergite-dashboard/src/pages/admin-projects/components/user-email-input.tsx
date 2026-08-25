import { ComboboxInput } from "@/components/ui/combobox-input";
import { userEmailsQuery } from "@/lib/api-client";
import { useQuery } from "@tanstack/react-query";
import * as React from "react";

/**
 * An email input that suggests addresses already known to MSS.
 *
 * Doubles as the row control for the member list, so it takes exactly the props a plain
 * input does and fetches its own suggestions.
 */
export function UserEmailInput(
  props: React.InputHTMLAttributes<HTMLInputElement>
) {
  const { data: emails = [] } = useQuery(userEmailsQuery());

  return <ComboboxInput {...props} suggestions={emails} />;
}
