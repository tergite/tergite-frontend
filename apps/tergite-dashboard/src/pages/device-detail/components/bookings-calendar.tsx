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
import { useContext, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Booking, User } from "types";
import timeGridPlugin from "@fullcalendar/timegrid";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";

/**
 * The calendar for viewing and making bookings
 *
 * @param props - the props to pass to the bookings calendar component
 * @returns - a react node representing the bookings calendar
 */
export function BookingsCalendar({
  bookings,
  backend,
  currentUser,
  isAdmin,
}: Props) {
  const { isDark } = useContext(AppStateContext);
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
    />
  );
}

interface Props {
  bookings: Booking[];
  backend: string;
  currentUser: User;
  isAdmin: boolean;
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

interface EventState {
  isDark?: boolean;
  currentUserId?: string;
  isAdmin: boolean;
}
