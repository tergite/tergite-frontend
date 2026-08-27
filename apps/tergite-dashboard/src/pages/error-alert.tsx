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

  return (
    <div
      id="error-page"
      className={cn(
        "flex h-full w-full items-center justify-center",
        className
      )}
    >
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">
            {displayedError.status ?? "Oops!"}
          </CardTitle>
          <CardDescription className="text-lg">
            Sorry, an unexpected error has occurred.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-destructive">
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
