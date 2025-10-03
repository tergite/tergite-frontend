import { EventCalendar } from "@/components/ui/event-calendar";
import { AppStateContext } from "@/lib/app-state";
import {
  DayCellContentArg,
  DayHeaderContentArg,
  EventContentArg,
  EventSourceInput,
} from "@fullcalendar/core";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverArrow,
} from "@/components/ui/popover";
import { DateTime, Duration } from "luxon";
import { useCallback, useContext, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Booking, NewBookingInfo, User } from "types";
import timeGridPlugin from "@fullcalendar/timegrid";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin, { DateClickArg } from "@fullcalendar/interaction";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  bookingsOfBackendQuery,
  createNewBooking,
  refreshBookingsQueries,
} from "@/lib/api-client";
import { toast } from "@/hooks/use-toast";

/**
 * The calendar for viewing and making bookings
 *
 * @param props - the props to pass to the bookings calendar component
 * @returns - a react node representing the bookings calendar
 */
export function BookingsCalendar({
  bookingsMetadata,
  backend,
  currentUser,
  isAdmin,
}: Props) {
  const queryClient = useQueryClient();
  const { isDark } = useContext(AppStateContext);
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
          backend,
          ...v,
        },
      })),
    [bookings, backend]
  );

  const currentUserId = currentUser.id;
  const getEventClassNames = useMemo(
    () =>
      getEventClassNamesGenerator({
        isAdmin,
        isDark,
        currentUserId,
      }),
    [isAdmin, isDark, currentUserId]
  );
  const renderEventContent = useMemo(
    () =>
      getEventContentGenerator({
        isAdmin,
        isDark,
        currentUserId,
      }),
    [isAdmin, isDark, currentUserId]
  );

  const bookingCreation = useMutation({
    mutationFn: useCallback(
      async (values: NewBookingInfo) => {
        return await createNewBooking(backend, values);
      },
      [backend]
    ),
    onSuccess: useCallback(
      async (booking: Booking) => {
        await refreshBookingsQueries(queryClient, backend);
        const startTime = DateTime.fromISO(booking.start_utc).toLocaleString(
          DateTime.DATETIME_SHORT
        );
        toast({ description: `Booking at ${startTime} created` });
      },
      [backend, queryClient]
    ),
    throwOnError: true,
  });

  const handleDateClick = useCallback(
    (info: DateClickArg) => {
      const title = prompt(`Enter event title:${info.dateStr}`);
      if (title) {
        const start_utc = info.dateStr;
        const end_utc = DateTime.fromISO(start_utc)
          .plus(Duration.fromObject({ seconds: 3600 }))
          .toISO();
        if (end_utc) {
          bookingCreation.mutate({ start_utc, end_utc });
        }
      }
    },
    [bookingCreation]
  );

  return (
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
    />
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
function getEventContentGenerator({ isAdmin, currentUserId }: EventState) {
  return (eventInfo: EventContentArg) => {
    const isPast = DateTime.fromISO(eventInfo.event.startStr) < DateTime.now();
    const isOwnedByUser =
      currentUserId === eventInfo.event.extendedProps.user_id;

    const canEdit = !isPast && (isOwnedByUser || isAdmin);
    return (
      <Popover>
        <PopoverTrigger asChild>
          <div className="fc-event-main border-1 px-2 w-full">
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
          <div>
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
              <div className="justify-end">
                {/* FIXME: Add onClick to allow to change the time if this event belongs to the user*/}
                {canEdit && (
                  <Button
                    variant="outline"
                    className="w-full"
                    disabled={isPast}
                  >
                    Edit
                  </Button>
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
  backend: string;
  currentUser: User;
  isAdmin: boolean;
}

interface EventState {
  isDark?: boolean;
  currentUserId?: string;
  isAdmin: boolean;
}

export interface BookingsMetadata {
  backend: string;
  user_id?: string;
  min_start_utc?: string;
  max_start_utc?: string;
  skip?: string;
  limit?: string;
}
