import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ErrorInfo } from "../../types";
import { cn } from "@/lib/utils";
import { useNavigate, useRouteError } from "react-router-dom";
import { PropsWithChildren } from "react";
import { ErrorBoundary, useErrorBoundary } from "react-error-boundary";

export default function ErrorAlert({ className = "", error }: Props) {
  const { resetBoundary } = useErrorBoundary();
  const routeError = useRouteError() as ErrorInfo;
  const navigate = useNavigate();
  const displayedError = error ?? routeError;
  // MSS restarting, under maintenance, or simply unreachable: not the user's problem to
  // decode, and worth saying plainly rather than as 'Failed to fetch'
  const isServiceUnavailable = displayedError?.status === 503;

  return (
    <div
      id="error-page"
      className={cn(
        "flex h-full w-full items-center justify-center",
        className
      )}
    >
      <Card data-cy-error-status={displayedError?.status}>
        <CardHeader>
          <CardTitle className="text-2xl">
            {isServiceUnavailable
              ? "Service unavailable"
              : (displayedError.status ?? "Oops!")}
          </CardTitle>
          <CardDescription className="text-lg">
            {isServiceUnavailable
              ? "The Tergite API is not answering. It may be restarting or under maintenance."
              : "Sorry, an unexpected error has occurred."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div
            className={
              isServiceUnavailable ? "text-muted-foreground" : "text-destructive"
            }
          >
            <i>
              {displayedError?.statusText ||
                displayedError?.message ||
                "Sorry, an unexpected error has occurred."}
            </i>
          </div>
        </CardContent>
        <CardFooter className="flex justify-between">
          <Button variant="default" onClick={resetBoundary}>
            Try again
          </Button>
          <Button variant="secondary" onClick={() => navigate(-1)}>
            Back
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}

interface Props {
  className?: string;
  error?: ErrorInfo;
}

export function ErrorBound({ children }: PropsWithChildren<ErrorBoundProps>) {
  return (
    <ErrorBoundary FallbackComponent={ErrorAlert}>{children}</ErrorBoundary>
  );
}

interface ErrorBoundProps {}
