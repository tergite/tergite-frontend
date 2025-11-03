import { EventCalendar } from "@/components/ui/event-calendar";
import { AppStateContext } from "@/lib/app-state";
import type {
  DayCellContentArg,
  DayHeaderContentArg,
  EventContentArg,
  EventDropArg,
  EventSourceInput,
} from "@fullcalendar/core";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverArrow,
} from "@/components/ui/popover";
import { DateTime, Duration } from "luxon";
import { useCallback, useContext, useMemo, useState } from "react";
import { Button, IconButton } from "@/components/ui/button";
import {
  Booking,
  BookingsConfig,
  ErrorInfo,
  GeneralMessage,
  User,
} from "types";
import timeGridPlugin from "@fullcalendar/timegrid";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin, { DateClickArg } from "@fullcalendar/interaction";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  bookingsOfBackendQuery,
  cancelBooking,
  createNewBooking,
  refreshBookingsQueries,
  updateBooking,
} from "@/lib/api-client";
import { BookingForm } from "./booking-form";
import { useToast } from "@/hooks/use-toast";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { AlertCircleIcon, XIcon } from "lucide-react";

/**
 * The calendar for viewing and making bookings
 *
 * @param props - the props to pass to the bookings calendar component
 * @returns - a react node representing the bookings calendar
 */
export function BookingsCalendar({
  bookingsMetadata,
  bookingsConfig,
  backend,
  currentUser,
  isAdmin,
}: Props) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { isDark } = useContext(AppStateContext);
  const [isCreateFormOpen, setIsCreateFormOpen] = useState(false);
  const [errMessage, setErrMessage] = useState<string>();
  const [isEditFormOpen, setIsEditFormOpen] = useState(false);
  const [currentBooking, setCurrentBooking] = useState<Booking>();
  const [defaultStartTimestamp, setDefaultStartTimestamp] = useState<string>();
  const currentUserId = currentUser.id;
  const { data: bookings = [] } = useQuery(
    bookingsOfBackendQuery(bookingsMetadata)
  );
  const calendarEvents = useMemo(
    (): EventSourceInput =>
      bookings.map((v) => ({
        title: v.username,
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

  /**
   * Handler to ger the classnames for the event
   *
   * This is useful for example in helping the events be responsive
   * to dark mode changes etc.
   */
  const getEventClassNames = useMemo(
    () =>
      getEventClassNamesGenerator({
        isAdmin,
        isDark,
        currentUserId,
      }),
    [isAdmin, isDark, currentUserId]
  );

  /**
   * Handler for generating custom components to
   * display the events on the calendar
   */
  const renderEventContent = useMemo(
    () =>
      getEventContentGenerator({
        isAdmin,
        isDark,
        currentUserId,
        handleBookingEdit,
        handleBookingCancel,
      }),
    [isAdmin, isDark, currentUserId, handleBookingEdit, handleBookingCancel]
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
  const handleEventDrop = useMutation({
    mutationFn: useCallback(
      async (arg: EventDropArg) => {
        // clear error message
        setErrMessage(undefined);

        const isPast = DateTime.fromISO(arg.event.startStr) < DateTime.now();
        const isOwnedByUser = currentUserId === arg.event.extendedProps.user_id;
        const canEdit = !isPast && (isOwnedByUser || isAdmin);
        if (!canEdit) {
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
        plugins={[timeGridPlugin, dayGridPlugin, interactionPlugin]}
        initialView="timeGridWeek"
        events={calendarEvents}
        views={{
          timeGridPlugin: {},
        }}
        eventContent={renderEventContent}
        eventClassNames={getEventClassNames}
        dayCellClassNames={getDayCellClassNames}
        slotLabelFormat={{
          hour12: false,
          hour: "2-digit",
        }}
        slotLabelClassNames="text-xs text-muted-foreground"
        dayHeaderFormat={{
          weekday: "short",
          day: "numeric",
        }}
        dayHeaderContent={getDayHeaderContent}
        nowIndicator={true}
        allDaySlot={false}
        businessHours={{
          start: "09:00",
          end: "17:00",
          daysOfWeek: [1, 2, 3, 4, 5],
        }}
        slotLaneClassNames="!h-10"
        firstDay={1}
        headerToolbar={{
          start: "title",
          center: "",
          end: "today,timeGridWeek,dayGridMonth prev,next",
        }}
        slotMinTime="00:00:00"
        slotMaxTime="24:00:00"
        scrollTime="09:00:00"
        contentHeight={"60vh"}
        dateClick={handleDateClick}
        editable={true}
        eventDrop={handleEventDrop.mutate}
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

/**
 * Creates an eventClassNames function basing on the current state
 *
 * @param state - the external state this event class generator depends on
 */
function getEventClassNamesGenerator(_props: EventState) {
  return (eventInfo: EventContentArg) => {
    const isPast = DateTime.fromISO(eventInfo.event.startStr) < DateTime.now();

    return isPast
      ? "border border-muted-foreground bg-muted-foreground hover:bg-muted"
      : "border border-foreground bg-[black] hover:bg-secondary";
  };
}

/**
 * Creates an EventContent generator function basing on the current state
 *
 * @param state - the external state this event class generator depends on
 */
function getEventContentGenerator({
  isAdmin,
  currentUserId,
  handleBookingEdit = () => {},
  handleBookingCancel = () => {},
}: EventState) {
  return (eventInfo: EventContentArg) => {
    const isPast = DateTime.fromISO(eventInfo.event.startStr) < DateTime.now();
    const isOwnedByUser =
      currentUserId === eventInfo.event.extendedProps.user_id;
    const booking = eventInfo.event.extendedProps as Booking;

    const canEdit = !isPast && (isOwnedByUser || isAdmin);
    return (
      <Popover>
        <PopoverTrigger asChild>
          <div
            data-cy-calendar-event
            className="fc-event-main border-1 px-2 w-full"
            data-booking-id={booking.id}
            data-booking-start={booking.start_utc}
            data-booking-end={booking.end_utc}
          >
            <div className="fc-event-main-frame text-secondary hover:text-secondary-foreground">
              <div className="fc-event-time">{eventInfo.timeText}</div>
              <div className="fc-event-title-container">
                <div className="fc-event-title fc-sticky">
                  {eventInfo.event.title}
                </div>
              </div>
            </div>
          </div>
        </PopoverTrigger>
        <PopoverContent>
          <div data-cy-event-details>
            <div className="grid gap-4">
              <div className="space-y-2">
                <h4 className="leading-none font-medium">
                  {eventInfo.event.title}
                </h4>
                <p className="text-muted-foreground text-sm">
                  {eventInfo.timeText}
                </p>
              </div>
              <div className="grid gap-2">
                <div className="">
                  <span className="text-muted-foreground pr-2">Device</span>
                  <span>{eventInfo.event.extendedProps.backend}</span>
                </div>
                <div className="">
                  <span className="text-muted-foreground pr-2">Duration</span>
                  <span>
                    {Duration.fromObject({
                      seconds: eventInfo.event.extendedProps.total_duration,
                    }).toHuman()}
                  </span>
                </div>
              </div>
              <div className="justify-between">
                {/* FIXME: Add onClick to allow to change the time if this event belongs to the user*/}
                {canEdit && (
                  <>
                    <Button
                      variant="outline"
                      className="w-1/2"
                      disabled={isPast}
                      onClick={() => handleBookingEdit(booking)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      className="w-1/2"
                      disabled={isPast}
                      onClick={() => handleBookingCancel(booking)}
                    >
                      Discard
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
          <PopoverArrow />
        </PopoverContent>
      </Popover>
    );
  };
}

interface Props {
  bookingsMetadata: BookingsMetadata;
  bookingsConfig: BookingsConfig;
  backend: string;
  currentUser: User;
  isAdmin: boolean;
}

interface EventState {
  isDark?: boolean;
  currentUserId?: string;
  isAdmin: boolean;
  handleBookingEdit?: (booking: Booking) => void;
  handleBookingCancel?: (booking: Booking) => void;
}

export interface BookingsMetadata {
  backend: string;
  user_id?: string;
  min_start_utc?: string;
  max_start_utc?: string;
  skip?: string;
  limit?: string;
}
