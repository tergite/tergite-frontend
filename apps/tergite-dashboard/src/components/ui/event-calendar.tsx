import FullCalendar from "@fullcalendar/react";
import { CalendarOptions } from "@fullcalendar/core";
import timeGridPlugin from "@fullcalendar/timegrid";

export default function EventCalendar({
  plugins = [timeGridPlugin],
  initialView = "timeGridWeek",
  ...props
}: Props) {
  return (
    <FullCalendar plugins={plugins} initialView={initialView} {...props} />
  );
}

interface Props extends CalendarOptions {}
