import { Button } from "@/components/ui/button";
import { DarkToggleBtn } from "@/components/ui/dark-toggle-btn";
import {
  FormField,
  Form,
  FormControl,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { getAuthProviders } from "@/lib/api/auth";
import { zodResolver } from "@hookform/resolvers/zod";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";
import type { AuthProviderResponse } from "@/lib/api/types";
import { z } from "zod";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { LogoMark } from "@/components/ui/logo-mark";

const formSchema = z.object({
  email: z.string().email("invalid email; expected xxx@bxxxx.xxx"),
});

export default function LoginForm() {
  const [providers, setProviders] = useState<AuthProviderResponse[]>();

  const signinForm = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { email: "" },
  });

  const onFormSubmit = useCallback(
    async (values: z.infer<typeof formSchema>) => {
      try {
        const authProviders = await getAuthProviders(values.email);
        setProviders(authProviders);
      } catch (error) {
        const message = (error as Error)?.message ?? String(error);
        signinForm.setError("email", { type: "custom", message });
      }
    },
    [signinForm, setProviders]
  );

  return (
    <main className="grid min-h-screen bg-background lg:grid-cols-[1.08fr_0.92fr]">
      <section className="relative hidden overflow-hidden bg-sidebar lg:block">
        <div className="absolute inset-0 bg-[url('/img/quantum-computer.jpg')] bg-cover bg-center opacity-45 mix-blend-luminosity" />
        <div className="quantum-grid absolute inset-0 opacity-50" />
        <div className="absolute inset-0 bg-gradient-to-b from-sidebar-veil/15 to-sidebar-veil/[0.92]" />
        <div className="relative flex h-full flex-col justify-between p-12 text-sidebar-highlight xl:p-16">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl border border-sidebar-highlight/20 bg-sidebar-highlight/10">
              <LogoMark className="h-7 w-7" />
            </span>
            <span className="font-display text-lg font-semibold tracking-[0.14em]">
              WACQT
            </span>
          </div>
          <div className="max-w-xl">
            <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-sidebar-primary/25 bg-sidebar-primary/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-sidebar-primary-soft">
              Quantum computer platform
            </span>
            <h1 className="text-5xl font-semibold leading-[1.08] tracking-tight xl:text-6xl">
              Precision control for quantum systems.
            </h1>
            <p className="mt-6 max-w-lg text-base leading-relaxed text-sidebar-soft">
              Monitor device health, manage compute access, and move
              experiments from queue to execution with confidence.
            </p>
          </div>
          <p className="text-xs text-sidebar-subtle">
            Wallenberg Centre for Quantum Technology
          </p>
        </div>
      </section>

      <section className="flex min-h-screen flex-col px-6 py-6 sm:px-12 lg:px-16 xl:px-24">
        <div className="flex w-full items-center justify-between">
          <div className="flex items-center gap-2 lg:hidden" data-cy-logo>
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-sidebar">
              <LogoMark className="h-6 w-6" />
            </span>
            <span className="font-display font-semibold tracking-[0.12em]">
              WACQT
            </span>
          </div>
          <DarkToggleBtn />
        </div>

        <div className="my-auto w-full max-w-md self-center py-16">
          <div className="mb-10">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
              Secure workspace
            </p>
            <h2 className="text-4xl font-semibold tracking-tight">
              Welcome back
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Sign in with your institutional email to access the quantum
              computer dashboard.
            </p>
          </div>
          {providers ? (
            providers.map((provider) => (
              <div
                key={provider.name}
                className="mb-2 grid gap-4"
              >
                <Button size="lg" asChild className="w-full justify-between">
                  <a
                    href={`${provider.url}?next=${window.location.origin}${import.meta.env.BASE_URL}`}
                    data-cy-login-link
                  >
                    Continue with {provider.name}
                    <ArrowRight className="h-4 w-4" />
                  </a>
                </Button>
              </div>
            ))
          ) : (
            <Form {...signinForm}>
              <form
                onSubmit={signinForm.handleSubmit(onFormSubmit)}
                noValidate
                className="grid gap-4"
              >
                <FormField
                  control={signinForm.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem className="grid gap-2">
                      <FormControl>
                        <Input
                          type="email"
                          placeholder="name@institution.se"
                          className="h-11 rounded-lg bg-card"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button
                  size="lg"
                  type="submit"
                  className="w-full justify-between"
                  disabled={!signinForm.formState.isDirty}
                >
                  Continue
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </form>
            </Form>
          )}
          {import.meta.env.DEV && (
            <p className="mt-6 text-center text-xs text-muted-foreground">
              <a
                href={`${import.meta.env.VITE_API_BASE_URL}/ui/dev-login.html`}
                className="font-medium text-primary hover:underline"
              >
                Log in as a seeded user (development only)
              </a>
            </p>
          )}
          <div className="mt-10 flex items-center justify-center gap-2 border-t pt-6 text-xs text-muted-foreground">
            <ShieldCheck className="h-4 w-4 text-signal" />
            Protected institutional access
          </div>
        </div>
      </section>
    </main>
  );
}
