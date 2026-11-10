import { useMemo } from "react";

export function Footer() {
  const currentYear = useMemo(() => new Date().getFullYear(), []);
  return (
    <p className="mx-auto my-5 text-xs text-muted-foreground">
      &copy; 2024-{currentYear} Chalmers Next Labs AB. All rights reserved.{" "}
      <a href={`${import.meta.env.BASE_URL}privacy.html`} className="underline">
        Privacy Policy
      </a>{" "}
      <a href={`${import.meta.env.BASE_URL}terms.html`} className="underline">
        Terms of Use
      </a>{" "}
    </p>
  );
}
