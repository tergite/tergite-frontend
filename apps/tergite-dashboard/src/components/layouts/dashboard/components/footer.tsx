import { useMemo } from "react";

export function Footer() {
  const currentYear = useMemo(() => new Date().getFullYear(), []);
  return (
    <p className="text-sm text-muted-foreground my-2 mx-auto">
      &copy; 2024-{currentYear} Chalmers Next Labs AB. All rights reserved.{" "}
      <a href="/privacy.html" className="underline">
        Privacy Policy
      </a>{" "}
      <a href="/terms.html" className="underline">
        Terms of Use
      </a>{" "}
    </p>
  );
}
