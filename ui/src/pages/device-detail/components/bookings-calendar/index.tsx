import { EventCalendar } from "@/components/ui/event-calendar";
import type {
  CalendarOptions,
  DayCellContentArg,
  DayHeaderContentArg,
  EventContentArg,
  EventDropArg,
  EventSourceInput,
} from "@fullcalendar/core";
import { DateTime } from "luxon";
import { useCallback, useMemo, useState } from "react";
import { IconButton } from "@/components/ui/button";
import type {
  Booking,
  BookingsConfig,
  GeneralMessage,
  User,
} from "@/lib/api/types";
import type { ErrorInfo } from "@/lib/api/client";
import timeGridPlugin from "@fullcalendar/timegrid";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin, { DateClickArg } from "@fullcalendar/interaction";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getBookingsOfBackendQuery,
  cancelBooking,
  createNewBooking,
  refreshBookingsQueries,
  updateBooking,
} from "@/lib/api/bookings";
import { BookingForm } from "./booking-form";
import { BookingEventContent } from "./event-content";
import { useToast } from "@/hooks/use-toast";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { AlertCircleIcon, XIcon } from "lucide-react";

const CALENDAR_OPTIONS: CalendarOptions = {
  plugins: [timeGridPlugin, dayGridPlugin, interactionPlugin],
  initialView: "timeGridWeek",
  views: { timeGridPlugin: {} },
  eventClassNames: getEventClassNames,
  dayCellClassNames: getDayCellClassNames,
  slotLabelFormat: { hour12: false, hour: "2-digit" },
  slotLabelClassNames: "text-xs text-muted-foreground",
  dayHeaderFormat: { weekday: "short", day: "numeric" },
  dayHeaderContent: getDayHeaderContent,
  nowIndicator: true,
  allDaySlot: false,
  businessHours: { start: "09:00", end: "17:00", daysOfWeek: [1, 2, 3, 4, 5] },
  slotLaneClassNames: "!h-10",
  firstDay: 1,
  headerToolbar: {
    start: "title",
    center: "",
    end: "today,timeGridWeek,dayGridMonth prev,next",
  },
  slotMinTime: "00:00:00",
  slotMaxTime: "24:00:00",
  scrollTime: "09:00:00",
  contentHeight: "60vh",
  editable: true,
};

/** The calendar for viewing and making bookings */
export function BookingsCalendar({
  bookingsMetadata,
  bookingsConfig,
  backend,
  currentUser,
  isAdmin,
}: Props) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [isCreateFormOpen, setIsCreateFormOpen] = useState(false);
  const [errMessage, setErrMessage] = useState<string>();
  const [isEditFormOpen, setIsEditFormOpen] = useState(false);
  const [currentBooking, setCurrentBooking] = useState<Booking>();
  const [defaultStartTimestamp, setDefaultStartTimestamp] = useState<string>();
  const currentUserId = currentUser.id;
  const { data: bookings = [] } = useQuery(
    getBookingsOfBackendQuery(bookingsMetadata)
  );
  const calendarEvents = useMemo(
    (): EventSourceInput =>
      bookings.map((v) => ({
        title: v.username ?? undefined,
        start: v.start_utc,
        end: v.end_utc,
        extendedProps: {
          ...v,
        },
      })),
    [bookings]
  );

  /**
   * Shows the error message to the user
   */
  const showErrorMsg = useCallback(
    (err: ErrorInfo | Error) => {
      setErrMessage(err.message);
      console.error(err);
    },
    [setErrMessage]
  );

  /**
   * Mutation hook for handling booking cancellation
   */
  const bookingCancellation = useMutation({
    mutationFn: useCallback(
      async ({ id }: Booking) => {
        return await cancelBooking(backend, id);
      },
      [backend]
    ),
    onSuccess: useCallback(
      async (response: GeneralMessage) => {
        await refreshBookingsQueries(queryClient, backend);
        toast({ description: response.detail });
      },
      [backend, queryClient, toast]
    ),
    onError: showErrorMsg,
  });

  /**
   * Handler for when editing a booking is initiated
   */
  const handleBookingEdit = useCallback(
    (booking: Booking) => {
      // clear error message
      setErrMessage(undefined);
      setCurrentBooking(booking);
      setIsEditFormOpen(true);
    },
    [setCurrentBooking, setIsEditFormOpen, setErrMessage]
  );

  /**
   * Handler for when canceling a booking is initiated
   */
  const handleBookingCancel = useCallback(
    (booking: Booking) => {
      // clear error message
      setErrMessage(undefined);
      return bookingCancellation.mutate(booking);
    },
    [bookingCancellation, setErrMessage]
  );

  const renderEventContent = useCallback(
    (eventInfo: EventContentArg) => (
      <BookingEventContent
        eventInfo={eventInfo}
        isEditable={isBookingEditable(
          eventInfo.event.extendedProps as Booking,
          currentUserId,
          isAdmin
        )}
        onEdit={handleBookingEdit}
        onCancel={handleBookingCancel}
      />
    ),
    [isAdmin, currentUserId, handleBookingEdit, handleBookingCancel]
  );

  /**
   * Handler to handle clicking empty slots in the calendar
   */
  const handleDateClick = useCallback(
    (info: DateClickArg) => {
      // clear error message
      setErrMessage(undefined);
      setDefaultStartTimestamp(info.dateStr);
      setIsCreateFormOpen(true);
    },
    [setDefaultStartTimestamp, setIsCreateFormOpen, setErrMessage]
  );

  /**
   * Handler to handle drag and drop of events
   */
  const bookingMove = useMutation({
    mutationFn: useCallback(
      async (arg: EventDropArg) => {
        // clear error message
        setErrMessage(undefined);

        const movedBooking = {
          ...(arg.event.extendedProps as Booking),
          start_utc: arg.event.startStr,
        };
        if (!isBookingEditable(movedBooking, currentUserId, isAdmin)) {
          return arg.revert();
        }
        const bookingId = arg.event.extendedProps.id;
        const newInfo = {
          start_utc: arg.event.start?.toISOString() as string,
          end_utc: arg.event.end?.toISOString() as string,
        };

        await updateBooking(backend, bookingId, newInfo);
      },
      [backend, isAdmin, currentUserId, setErrMessage]
    ),
    onSuccess: useCallback(async () => {
      await refreshBookingsQueries(queryClient, backend);
    }, [backend, queryClient]),
    onError: showErrorMsg,
  });

  /**
   * Handles the click on the alert close button
   */
  const handleAlertClose = useCallback(() => {
    setErrMessage(undefined);
  }, [setErrMessage]);

  /**
   * Handles errors when they occur while creating boking
   */
  const handleBookingCreateError = useCallback(
    (err: ErrorInfo | Error) => {
      showErrorMsg(err);
      setIsCreateFormOpen(false);
    },
    [showErrorMsg, setIsCreateFormOpen]
  );

  /**
   * Handles errors when they occur while editing boking
   */
  const handleBookingEditError = useCallback(
    (err: ErrorInfo | Error) => {
      showErrorMsg(err);
      setIsEditFormOpen(false);
    },
    [showErrorMsg, setIsEditFormOpen]
  );

  return (
    <>
      {errMessage && (
        <Alert variant="destructive" className="mb-2">
          <div className="flex gap-2 items-start">
            <AlertCircleIcon />
            <AlertTitle className="mt-1">{errMessage}</AlertTitle>
            <IconButton
              variant="outline"
              Icon={XIcon}
              className="ml-auto h-5 w-5"
              iconClassName="h-3 w-3"
              onClick={handleAlertClose}
            />
          </div>
        </Alert>
      )}
      <EventCalendar
        {...CALENDAR_OPTIONS}
        events={calendarEvents}
        eventContent={renderEventContent}
        dateClick={handleDateClick}
        eventDrop={bookingMove.mutate}
      />
      <BookingForm
        dialogTitle="Create new booking"
        open={isCreateFormOpen}
        onOpenChange={setIsCreateFormOpen}
        backend={backend}
        bookingsConfig={bookingsConfig}
        defaultStartTimestamp={defaultStartTimestamp}
        mutate={(backend, newInfo) => createNewBooking(backend, newInfo)}
        onError={handleBookingCreateError}
      />
      {currentBooking && (
        <BookingForm
          dialogTitle="Edit booking"
          open={isEditFormOpen}
          onOpenChange={setIsEditFormOpen}
          backend={backend}
          bookingsConfig={bookingsConfig}
          initialBooking={currentBooking}
          mutate={(backend, newInfo, original) =>
            updateBooking(backend, original?.id as string, newInfo)
          }
          onSuccess={setCurrentBooking}
          onError={handleBookingEditError}
        />
      )}
    </>
  );
}

/**
 * Gets the day header component for display
 *
 * @param arg - the object containing the information about the day header cell
 * @returns - the deay header cell component
 */
function getDayHeaderContent(arg: DayHeaderContentArg) {
  // Customize the header cell content
  const date = arg.date;
  const dayName = date.toLocaleDateString("en-US", { weekday: "short" });
  const dayNumber = date.getDate();
  return (
    <div className="flex flex-col items-center justify-center py-2">
      <span className="text-xs font-light">{dayName}</span>
      <span className="text-sm font-semibold">{dayNumber}</span>
    </div>
  );
}

/**
 * Generates the class names for the day cells
 *
 * @param arg - the object with information about the day cell
 */
function getDayCellClassNames(arg: DayCellContentArg) {
  return arg.isToday ? ["!bg-muted"] : [];
}

function getEventClassNames(eventInfo: EventContentArg) {
  const isPast = DateTime.fromISO(eventInfo.event.startStr) < DateTime.now();
  return isPast
    ? "border border-muted-foreground bg-muted-foreground hover:bg-muted"
    : "border border-foreground bg-[black] hover:bg-secondary";
}

/** A booking is editable by its owner or an admin, until it starts */
function isBookingEditable(
  booking: Booking,
  userId: string,
  isAdmin: boolean
): boolean {
  const isPast = DateTime.fromISO(booking.start_utc) < DateTime.now();
  return !isPast && (booking.user_id === userId || isAdmin);
}

interface Props {
  bookingsMetadata: BookingsMetadata;
  bookingsConfig: BookingsConfig;
  backend: string;
  currentUser: User;
  isAdmin: boolean;
}

export interface BookingsMetadata {
  backend: string;
  user_id?: string;
  min_start_utc?: string;
  max_start_utc?: string;
  skip?: number;
  limit?: number;
}
