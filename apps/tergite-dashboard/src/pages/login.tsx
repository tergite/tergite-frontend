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
import { type AuthProviderResponse } from "@/lib/api/types";
import { z } from "zod";

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
    <main className=" grid gap-4 p-4 md:gap-8 grid-cols-1 lg:grid-cols-2 h-screen">
      <div className="w-full h-full hidden lg:block m-4 rounded-md my-auto bg-[url('/img/quantum-computer.jpg')] bg-no-repeat bg-center bg-cover"></div>
      <div className="w-full">
        <div className="w-full text-right">
          <DarkToggleBtn />
        </div>
        <div className="my-40 p-4 ">
          <div data-cy-logo className="text-center">
            <p className="text-3xl font-bold mb-2">WACQT</p>

            <p className="font-light text-lg">
              Wallenberg Centre for <br /> Quantum Technology
            </p>
            <span className="sr-only">
              WACQT: Wallenberg Centre for Quantum Technology
            </span>
          </div>
        </div>

        <div className="w-full">
          <h2 className="text-3xl mb-4 text-center font-semibold">
            Welcome back
          </h2>
          <div className="pb-5 border-b mx-auto max-w-48 mb-20 text-center">
            <h2 className="text-xl font-thin">Sign in</h2>
          </div>

          {providers ? (
            providers.map((provider) => (
              <div
                key={provider.name}
                className="grid gap-4 w-2/3 mx-auto max-w-80 mb-2"
              >
                <Button variant="outline" asChild>
                  <a
                    href={`${provider.url}?next=${window.location.origin}${import.meta.env.BASE_URL}`}
                    data-cy-login-link
                  >
                    Login with {provider.name}
                  </a>
                </Button>
              </div>
            ))
          ) : (
            <Form {...signinForm}>
              <form
                onSubmit={signinForm.handleSubmit(onFormSubmit)}
                className="grid gap-4 w-2/3 mx-auto max-w-80"
              >
                <FormField
                  control={signinForm.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem className="grid gap-2">
                      <FormControl>
                        <Input placeholder="Email address:" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" disabled={!signinForm.formState.isDirty}>
                  Next
                </Button>
              </form>
            </Form>
          )}
        </div>
      </div>
    </main>
  );
}
