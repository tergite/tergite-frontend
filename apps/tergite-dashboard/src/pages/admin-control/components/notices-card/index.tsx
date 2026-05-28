import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import NoticeForm from "./form";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { DateTime } from "luxon";
import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { noticeCountQuery, noticesQuery } from "@/lib/api-client";
import { AdminNoticeBanner } from "./banner";

export function NoticesCard() {
  const [page, setPage] = useState(1);
  const currentTimestamp = useMemo(() => DateTime.now().toISO(), [page]);
  const filters = {
    max_start_utc: currentTimestamp,
    min_expires_utc: currentTimestamp,
    include_dismissed: true,
  };

  const { data: notices, isPlaceholderData } = useQuery(
    noticesQuery({
      ...filters,
      sort: ["severity_number", "starts_at"],
      limit: 1,
      skip: page - 1,
    }),
  );
  const { data: noticeCount } = useQuery(noticeCountQuery(filters));

  const handlePaginationNext = useCallback(
    () => setPage((old) => old + 1),
    [setPage],
  );

  const handlePaginationPrevious = useCallback(
    () => setPage((old) => old - 1),
    [setPage],
  );

  return (
    <Card className="h-full" data-testid="notices-card">
      <CardHeader className="pb-3">
        <CardDescription>Notices</CardDescription>
        <div className="flex items-center justify-between">
          {noticeCount && noticeCount > 0 && (
            <Badge variant="secondary">{noticeCount} active</Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {/* Active banners */}
        {notices?.length === 0 ? (
          <div className="rounded-md border border-dashed p-3 text-center">
            <p className="text-sm text-muted-foreground">No active notices</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {notices?.map((notice) => (
              <AdminNoticeBanner key={notice.id} notice={notice} />
            ))}
          </div>
        )}
        <PaginationControl
          currentPage={page}
          onNext={handlePaginationNext}
          onPrevious={handlePaginationPrevious}
          isNextDisabled={isPlaceholderData || page >= (noticeCount ?? 0)}
          isPreviousDisabled={page <= 1}
        />
        <NoticeForm />
      </CardContent>
    </Card>
  );
}

function PaginationControl({
  onNext,
  onPrevious,
  currentPage,
  isNextDisabled,
  isPreviousDisabled,
}: PaginationProps) {
  const disabledClass = "pointer-events-none opacity-50";
  const enabledClass = "cursor-pointer";
  return (
    <Pagination className="flex justify-end">
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious
            onClick={onPrevious}
            className={isPreviousDisabled ? disabledClass : enabledClass}
            aria-disabled={isPreviousDisabled}
            iconOnly={true}
          />
        </PaginationItem>
        <PaginationItem>
          <PaginationLink isActive>{currentPage}</PaginationLink>
        </PaginationItem>

        <PaginationItem>
          <PaginationNext
            onClick={onNext}
            className={isNextDisabled ? disabledClass : enabledClass}
            aria-disabled={isNextDisabled}
            iconOnly={true}
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
}

interface PaginationProps {
  onNext?: () => void;
  onPrevious?: () => void;
  currentPage: number;
  isNextDisabled: boolean;
  isPreviousDisabled: boolean;
}

