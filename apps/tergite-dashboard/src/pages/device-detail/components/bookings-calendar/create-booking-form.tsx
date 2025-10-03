// import {
//   Card,
//   CardHeader,
//   CardTitle,
//   CardContent,
//   CardFooter,
// } from "@/components/ui/card";
// import { cn } from "@/lib/utils";
// import { useMutation } from "@tanstack/react-query";
// import { AdminProject } from "types";
// import { useCallback } from "react";
// import { Button, IconButton } from "@/components/ui/button";
// import { z } from "zod";
// import { useForm } from "react-hook-form";
// import { zodResolver } from "@hookform/resolvers/zod";
// import {
//   Form,
//   FormControl,
//   FormField,
//   FormItem,
//   FormMessage,
// } from "@/components/ui/form";
// import { Label } from "@/components/ui/label";
// import { Input } from "@/components/ui/input";
// import { Switch } from "@/components/ui/switch";
// import { Textarea } from "@/components/ui/textarea";
// import { MultiInput } from "@/components/ui/multi-input";
// import { useToast } from "@/hooks/use-toast";
// import { createAdminProject } from "@/lib/api-client";
// import { DateTime } from "luxon";
// import { X } from "lucide-react";

// const formSchema = z.object({
//   startDate: z.date(),
//   time: z.object({
//     hour: z.number().int(),
//     minute: z.number().int(),
//     second: z.number().int(),
//     millisecond: z.number().int().optional(),
//   }),
// });

// export function CreateProjectForm({
//   className = "",
//   onCreate,
//   onCancel = () => {},
//   onClose,
// }: Props) {
//   const { toast } = useToast();
//   const now = DateTime.now();

//   const createForm = useForm<z.infer<typeof formSchema>>({
//     resolver: zodResolver(formSchema),
//     defaultValues: {
//       name: `${now.toLocaleString()} project`,
//       description: `Project created on ${now.toLocaleString()}`,
//       is_active: true,
//       qpu_seconds: 0,
//       admin_email: "",
//       user_emails: [],
//       ext_id: `project-${now.toMillis()}`,
//     },
//   });

//   const projectCreation = useMutation({
//     mutationFn: async (values: z.infer<typeof formSchema>) => {
//       return await createAdminProject(values);
//     },
//     onSuccess: useCallback(
//       async (project: AdminProject) => {
//         await onCreate(project);
//         toast({ description: `Project ${project.name} created` });
//       },
//       [onCreate, toast]
//     ),
//     throwOnError: true,
//   });

//   const handleCancel = useCallback(async () => {
//     createForm.reset();
//     onCancel();
//   }, [createForm, onCancel]);

//   // A hack: for some reason editForm.formState.isDirty was not always right especially
//   //   when one clicked on another project when they had just editted only the user_emails field but not submitted
//   //   if the new project had everything in common with the project, except say the user_emails, editForm.formState.isDirty
//   //   would still show that it is dirty yet it should reset whenever new values are passed to it during initialization
//   const isFormDirty = Object.keys(createForm.formState.dirtyFields).length;

//   return (
//     <Form {...createForm}>
//       <form
//         onSubmit={createForm.handleSubmit((values) => {
//           return projectCreation.mutate(values);
//         })}
//         onReset={handleCancel}
//         className={cn("overflow-hidden", className)}
//       >
//         <Card id="create-project">
//           <CardHeader className="flex flex-row items-center bg-muted/50 justify-between space-y-0">
//             <div className="grid gap-0.5">
//               <CardTitle className="group flex items-center gap-2 text-lg">
//                 New project
//               </CardTitle>
//             </div>
//             <IconButton Icon={X} variant="ghost" onClick={onClose} />
//           </CardHeader>
//           <CardContent className="p-6 text-sm xl:max-h-[60vh] overflow-y-auto">
//             <div className="grid gap-3">
//               <ul className="grid gap-4">
//                 <FormField
//                   control={createForm.control}
//                   name="name"
//                   render={({ field }) => (
//                     <FormItem className="">
//                       <FormControl>
//                         <div className="">
//                           <Label
//                             className="text-muted-foreground"
//                             htmlFor="name"
//                           >
//                             Name
//                           </Label>
//                           <Input id="name" type="string" {...field} />
//                         </div>
//                       </FormControl>
//                       <FormMessage />
//                     </FormItem>
//                   )}
//                 />

//                 <FormField
//                   control={createForm.control}
//                   name="ext_id"
//                   render={({ field }) => (
//                     <FormItem className="">
//                       <FormControl>
//                         <div className="">
//                           <Label
//                             className="text-muted-foreground"
//                             htmlFor="ext_id"
//                           >
//                             External ID
//                           </Label>
//                           <Input id="ext_id" type="string" {...field} />
//                         </div>
//                       </FormControl>
//                       <FormMessage />
//                     </FormItem>
//                   )}
//                 />

//                 <FormField
//                   control={createForm.control}
//                   name="description"
//                   render={({ field }) => (
//                     <FormItem className="">
//                       <FormControl>
//                         <div className="">
//                           <Label
//                             className="mr-2 text-muted-foreground"
//                             htmlFor="description"
//                           >
//                             Description
//                           </Label>
//                           <Textarea id="description" {...field} rows={4} />
//                         </div>
//                       </FormControl>
//                       <FormMessage />
//                     </FormItem>
//                   )}
//                 />

//                 <FormField
//                   control={createForm.control}
//                   name="is_active"
//                   render={({ field }) => (
//                     <FormItem className="">
//                       <FormControl>
//                         <div className="flex justify-between">
//                           <Label
//                             className="mr-2 text-muted-foreground"
//                             htmlFor="is_active"
//                           >
//                             Live
//                           </Label>
//                           <Switch
//                             id="is_active"
//                             onCheckedChange={field.onChange}
//                             checked={field.value}
//                             disabled
//                             aria-disabled
//                           />
//                         </div>
//                       </FormControl>
//                       <FormMessage />
//                     </FormItem>
//                   )}
//                 />

//                 <FormField
//                   control={createForm.control}
//                   name="qpu_seconds"
//                   render={() => (
//                     <FormItem className="">
//                       <FormControl>
//                         <div className="">
//                           <Label
//                             className="text-muted-foreground"
//                             htmlFor="qpu_seconds"
//                           >
//                             QPU seconds
//                           </Label>
//                           <Input
//                             id="qpu_seconds"
//                             type="number"
//                             {...createForm.register("qpu_seconds", {
//                               valueAsNumber: true,
//                             })}
//                           />
//                         </div>
//                       </FormControl>
//                       <FormMessage />
//                     </FormItem>
//                   )}
//                 />

//                 <FormField
//                   control={createForm.control}
//                   name="admin_email"
//                   render={({ field }) => (
//                     <FormItem className="">
//                       <FormControl>
//                         <div className="">
//                           <Label
//                             className="text-muted-foreground"
//                             htmlFor="admin_email"
//                           >
//                             Admin email
//                           </Label>
//                           <Input id="admin_email" type="email" {...field} />
//                         </div>
//                       </FormControl>
//                       <FormMessage />
//                     </FormItem>
//                   )}
//                 />

//                 <FormField
//                   control={createForm.control}
//                   name="user_emails"
//                   render={({ field }) => (
//                     <FormItem className="">
//                       <FormControl>
//                         <div className="flex flex-col">
//                           <Label
//                             className="text-muted-foreground mb-1"
//                             htmlFor="user_emails"
//                           >
//                             Member emails
//                           </Label>
//                           <MultiInput
//                             id="user_emails"
//                             type="email"
//                             {...field}
//                           />
//                         </div>
//                       </FormControl>
//                       <FormMessage />
//                     </FormItem>
//                   )}
//                 />
//               </ul>
//             </div>
//           </CardContent>
//           <CardFooter className="grid grid-cols-2 gap-2 border-t bg-muted/50 px-6 py-3">
//             <Button
//               disabled={projectCreation.isPending || !isFormDirty}
//               type="submit"
//               variant="default"
//             >
//               Submit
//             </Button>

//             <Button
//               type="reset"
//               disabled={projectCreation.isPending}
//               variant="secondary"
//               className="border"
//             >
//               Cancel
//             </Button>
//           </CardFooter>
//         </Card>
//       </form>
//     </Form>
//   );
// }

// interface Props {
// className?: string;
// onCreate: (project: AdminProject) => Promise<void>;
// onCancel?: () => void;
// onClose: () => void;
// }
