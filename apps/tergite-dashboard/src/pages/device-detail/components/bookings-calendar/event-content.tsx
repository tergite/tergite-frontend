import type { EventContentArg } from "@fullcalendar/core";
import { Duration } from "luxon";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverArrow,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { Booking } from "@/lib/api/types";

/** A booking on the calendar, with its details and actions in a popover */
export function BookingEventContent({
  eventInfo,
  isEditable,
  onEdit,
  onCancel,
}: Props) {
  const booking = eventInfo.event.extendedProps as Booking;

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
              <div>
                <span className="text-muted-foreground pr-2">Device</span>
                <span>{booking.backend}</span>
              </div>
              <div>
                <span className="text-muted-foreground pr-2">Duration</span>
                <span>
                  {Duration.fromObject({
                    seconds: booking.total_duration,
                  }).toHuman()}
                </span>
              </div>
            </div>
            <div className="justify-between">
              {isEditable && (
                <>
                  <Button
                    variant="outline"
                    className="w-1/2"
                    onClick={() => onEdit(booking)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="destructive"
                    className="w-1/2"
                    onClick={() => onCancel(booking)}
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
}

interface Props {
  eventInfo: EventContentArg;
  isEditable: boolean;
  onEdit: (booking: Booking) => void;
  onCancel: (booking: Booking) => void;
}
