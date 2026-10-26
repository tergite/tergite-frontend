import {
  DateTime,
  Duration,
  DurationLike,
  DurationLikeObject,
  DurationUnit,
} from "luxon";

// luxon's relative format gives up past about 273,000 years
const MAX_YEARS = 273_000;

/** @returns undefined where the string holds no integer */
export function parseOptionalInt(value: string): number | undefined {
  const result = parseInt(value);
  return isNaN(result) ? undefined : result;
}

/** Parses an ISO time string (HH:mm[:ss][.SSSSSS]) */
export function extractTime(value: string): Time {
  const timeRegex = /(\d\d):(\d\d)(:(\d\d))?(\.(\d+))?/;
  const [
    _wholeValue,
    hourStr,
    minuteStr,
    _colonAndSeconds,
    secondStr,
    _pointAndMillisecons,
    millisecondStr,
  ] = timeRegex.exec(value) ?? [];
  return {
    hour: parseOptionalInt(hourStr),
    minute: parseOptionalInt(minuteStr),
    second: parseOptionalInt(secondStr),
    millisecond: parseOptionalInt(millisecondStr),
  };
}

/** Formats a Time as an ISO time string (HH:mm[:ss][.SSSSSS]) */
export function formatTime({
  hour,
  minute,
  second,
  millisecond,
}: Time): string {
  const paddedMinute = `${minute}`.padStart(2, "0");
  const paddedSecond = `${second}`.padStart(2, "0");
  const paddedHour = `${hour}`.padStart(2, "0");
  const secondStr = second === undefined ? "" : `:${paddedSecond}`;
  const secondsAndMilliseconds =
    millisecond === undefined
      ? secondStr
      : `${secondStr || "00"}.${millisecond}`; // if milliseconds exist without seconds, have 00 as seconds

  return `${paddedHour}:${paddedMinute}${secondsAndMilliseconds}`;
}

/** A relative datetime string like 'in 5 days', even where luxon gives up */
export function formatRelative(date: DateTime): string {
  return date.toRelative() ?? `in +${MAX_YEARS.toLocaleString()} years`;
}

/** Combines a date and a time into one DateTime */
export function mergeDatetime(value: {
  date?: Date;
  time?: Time | DateTime;
}): DateTime {
  const { date = new Date(), time = {} } = value;
  const { hour, minute, second, millisecond } = time;
  return DateTime.fromJSDate(date).set({ hour, minute, second, millisecond });
}

/**
 * Splits a duration over the units from maxUnit down to minUnit, each a whole number,
 * which luxon's Duration does not do
 */
export function convertToInputDuration(
  value: DurationLike,
  options: { maxUnit?: keyof InputDuration; minUnit?: keyof InputDuration } = {}
): InputDuration & Duration {
  const durationValue = Duration.fromDurationLike(value);
  const { maxUnit = "days", minUnit = "milliseconds" } = options;

  const units: DurationUnit[] = [
    "days",
    "hours",
    "minutes",
    "seconds",
    "milliseconds",
  ];
  const startIndex = units.indexOf(maxUnit);
  const endIndex = units.indexOf(minUnit) + 1;

  const durationLikeObj: DurationLikeObject = {};
  for (const unit of units.slice(startIndex, endIndex)) {
    durationLikeObj[unit] = Math.trunc(
      durationValue.minus(durationLikeObj).as(unit)
    );
  }

  return Duration.fromObject(durationLikeObj);
}

export type Time = {
  hour?: number;
  minute?: number;
  second?: number;
  millisecond?: number;
};

export type InputDuration = {
  days?: number;
  hours?: number;
  minutes?: number;
  seconds?: number;
  milliseconds?: number;
};
