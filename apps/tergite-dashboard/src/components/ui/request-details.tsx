import { DetailItem } from "@/components/ui/detail-item";
import { getUserRequestDetails } from "@/lib/user-requests";
import type { AnyValue } from "@/lib/user-requests";
import type { UserRequest } from "@/lib/api/types";

/** What the request asks for, as each of its parties sees it */
export function RequestDetails({ request }: Props) {
  return (
    <div data-cy-request-body className="grid gap-3">
      <div className="font-semibold">Request</div>
      <ul className="grid gap-3">
        {Object.entries(getUserRequestDetails(request)).map(([key, value]) => (
          <DetailItem key={key} label={formatLabel(key)}>
            {formatValue(value)}
          </DetailItem>
        ))}
      </ul>
    </div>
  );
}

interface Props {
  request: UserRequest;
}

function formatLabel(key: string): string {
  const words = key.replace(/_|-/g, " ");
  return words.charAt(0).toUpperCase().concat(words.slice(1));
}

function formatValue(value: AnyValue): string {
  return Array.isArray(value) ? value.join(", ") : `${value}`;
}
