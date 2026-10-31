import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "./card";

export function SidebarPlaceholder({
  mainTitle,
  contentDetail,
  contentTitle,
  className,
}: Props) {
  return (
    <Card
      id="sidebar-placeholder"
      className={cn(
        "overflow-hidden order-first xl:order-none col-span-1",
        className
      )}
    >
      <CardHeader className="flex flex-row items-start bg-muted/50 justify-between">
        <div className="grid gap-0.5">
          <CardTitle className="group flex items-center gap-2 text-lg">
            {mainTitle}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-6 text-sm">
        <div className="grid gap-3">
          <div className="font-semibold">{contentTitle}</div>
          <div className="text-muted-foreground">{contentDetail}</div>
        </div>
      </CardContent>
    </Card>
  );
}

interface Props {
  mainTitle: string;
  contentTitle: string;
  contentDetail: string;
  className?: string;
}
