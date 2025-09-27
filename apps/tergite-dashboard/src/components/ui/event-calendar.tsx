import FullCalendar from "@fullcalendar/react";
import { CalendarOptions } from "@fullcalendar/core";
import dayGridPlugin from "@fullcalendar/daygrid";

export default function EventCalendar({
  plugins,
  initialView,
  ...props
}: Props) {
  return (
    <FullCalendar
      plugins={[dayGridPlugin]}
      initialView="dayGridMonth"
      {...props}
    />
  );
}

interface Props extends CalendarOptions {}
