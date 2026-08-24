import { userEmailsQuery } from "@/lib/api-client";
import { useQuery } from "@tanstack/react-query";

export const USER_EMAILS_DATALIST_ID = "user-emails";

/**
 * The address suggestions behind the admin email inputs.
 *
 * A datalist rather than a combobox: the field still takes any address a superuser
 * types, including one for a user who has not logged in yet, and suggestions are a
 * convenience on top rather than a constraint.
 */
export function UserEmailsDatalist() {
  const { data: emails = [] } = useQuery(userEmailsQuery());

  return (
    <datalist id={USER_EMAILS_DATALIST_ID} data-cy-user-emails>
      {emails.map((email) => (
        <option key={email} value={email} />
      ))}
    </datalist>
  );
}
