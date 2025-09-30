import FullCalendar from "@fullcalendar/react";
import { CalendarOptions } from "@fullcalendar/core";
import dayGridPlugin from "@fullcalendar/daygrid";

export default function EventCalendar({
  plugins = [dayGridPlugin],
  initialView = "dayGridMonth",
  ...props
}: Props) {
  return (
    <FullCalendar plugins={plugins} initialView={initialView} {...props} />
  );
}

interface Props extends CalendarOptions {}
