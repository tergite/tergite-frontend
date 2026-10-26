# Tergite Dashboard — System Design

The web client of the Tergite stack: a React single-page app that shows the state of the
quantum computers and lets users manage projects, API tokens, bookings and (for admins)
backends, QPU-time requests and notices.

Read [../../DESIGN.md](../../DESIGN.md) first for the monorepo context, deployment and the
cross-app conventions.

The dashboard has **no backend of its own**. In production it is a static bundle MSS serves
at `/ui`; every piece of data comes from MSS over HTTP with a cookie. The Express server in
`dev/mock-api/` is a development and testing mock only — it is never deployed.

## 1. Architecture: co-located hierarchy

The organising principle is **proximity of use**. A component lives as close as possible to
the single place that uses it, and only moves outward when a second consumer appears.

```
src/
├── main.tsx                 # ReactDOM root
├── app.tsx                  # builds the router once; QueryClientProvider + RouterProvider
├── router.tsx               # the module-level route array: every route, its element, its loader
├── index.css                # Tailwind layers + CSS custom properties (light/dark)
├── lib/
│   ├── api/
│   │   ├── client.ts        # the typed openapi-fetch client: the only file that talks HTTP
│   │   ├── schema.d.ts      # generated from MSS's OpenAPI schema by `npm run generate:api`
│   │   └── devices.ts, …    # one module per resource: its queryOptions and mutations
│   ├── app-state.ts         # useAppStore, the zustand store of app state
│   ├── query-client.ts      # the one QueryClient, polling by default
│   ├── loaders.ts           # loadOrRedirectIfAuthErr and tryQueryFetchMany, for route loaders
│   ├── time.ts              # parsing and formatting times and durations beyond one luxon call
│   ├── user-requests.ts     # a request's title and details, as every request view shows them
│   └── utils.ts             # cn, and nothing else
├── hooks/
│   └── use-toast.ts
├── components/
│   ├── ui/                  # generic, page-agnostic primitives (shadcn/ui + our own)
│   │   ├── data-table/      # the shared table: index, filter-form, sort-header, table-row
│   │   └── __tests__/
│   └── layouts/
│       └── dashboard/
│           ├── index.tsx    # the layout shell + its loader
│           └── components/  # footer, sidebar, top-banner, topbar/
└── pages/
    ├── devices.tsx          # a single-file page
    ├── login.tsx
    ├── error-alert.tsx
    ├── home/
    │   ├── index.tsx        # the page + its loader
    │   └── components/
    │       ├── devices-table/{index,columns}.tsx
    │       ├── jobs-table/{index,columns,filter-form,detail-drawer}.tsx
    │       └── bookings-table/{index,columns,filter-form}.tsx
    ├── device-detail/
    │   ├── index.tsx
    │   └── components/
    │       ├── device-summary.tsx            # leaf → a file
    │       ├── calibration-data-table.tsx
    │       ├── bookings-calendar/            # has children → a folder
    │       │   ├── index.tsx
    │       │   └── booking-form.tsx
    │       └── calibration-bar-chart/
    │           ├── index.tsx
    │           └── calibration-bar.tsx
    ├── projects/, tokens/, requests/, admin-control/, admin-projects/, admin-requests/
types.ts                     # all shared TypeScript types (repo root of the app)
```

### The rule

1. A page is `src/pages/{page-name}/index.tsx`. If it has no children of its own it may be a
   single file, `src/pages/{page-name}.tsx` (`devices.tsx`, `login.tsx`).
2. Components used **only** by that page live in `src/pages/{page-name}/components/`.
3. The same rule recurses. A component that itself has children becomes a folder with
   `index.tsx` plus its children beside it; a leaf component stays a single file.
   `device-detail/components/bookings-calendar/booking-form.tsx` is only reachable from the
   bookings calendar, which is only reachable from the device-detail page, and the directory
   path says exactly that.
4. A component is promoted to `src/components/ui/` **when and only when** a second, unrelated
   consumer appears. `ui/` is for things with no knowledge of any particular page —
   `Button`, `DataTable`, `Card`, `DonutChart`, `EventCalendar`.
5. `src/components/layouts/` is for shells that wrap routes rather than being routed to. It
   follows the same recursion: `layouts/dashboard/components/topbar/` is a folder because the
   topbar has its own `breadcrumb.tsx` and `mobile-menu.tsx`.

Note that `detail-item.tsx` exists both in `components/ui/` and in
`pages/device-detail/components/` — the page-specific one is a different component that
happens to share a name. That is the layout working as intended: no need to generalise a
component to reuse a name.

### Why

You can delete a feature by deleting one directory. You can see a component's blast radius
from its path. Nothing accumulates in a global `components/` bucket that nobody dares touch
because its consumers are unknown. The cost is a deeper tree and some near-duplication
between sibling pages, which is accepted deliberately — duplication is cheaper here than a
premature abstraction shared by two pages that then diverge.

### Table sub-convention

Any page listing records uses the shared `DataTable` and splits the work the same way:

| File | Contains |
| --- | --- |
| `index.tsx` | the thin wrapper that passes `columns`, `data`, `filterFormProps`, `getDrawerContent` to `DataTable` |
| `columns.tsx` | the `ColumnDef[]` — cell rendering, `SortHeader`, `meta.headerClassName` |
| `filter-form.tsx` | the `DataTableFormConfig` describing the filter popover fields |
| `detail-drawer.tsx` | the drawer body rendered when a row is clicked (where the page has one) |

The pattern is visible in `home/components/jobs-table/`, `tokens/components/tokens-table/`,
`projects/components/project-table/`, `admin-projects/components/projects-table/` and
`admin-requests/components/requests-table/`. Follow it for a new table rather than inventing
a variant.

Pages with a master/detail split additionally have a `*-sidebar/` folder holding the detail
panel and its dialogs (`tokens/components/tokens-sidebar/{index,delete-dialog,lifespan-dialog}.tsx`).

## 2. Data flow

```mermaid
flowchart TD
    Route["route in router.tsx"] -->|"loader(queryClient)"| Loader
    Loader -->|"ensureQueryData(...)"| RQ["react-query cache"]
    RQ -->|"queryFn"| AC["lib/api/{resource}.ts"]
    AC -->|"client.GET(path, params)"| Client["lib/api/client.ts"]
    Client -->|"fetch, credentials: include"| MSS[(MSS)]
    Loader -->|"returns typed *Data object"| Page["page component"]
    Page -->|"useLoaderData() as XData"| Initial["initial render, no spinner"]
    Page -->|"useQuery(sameQueryOptions)"| RQ
    RQ -->|"refetchInterval"| Live["live updates"]
    Page -->|"useMutation(action fn)"| AC
    AC -->|"then refreshXQueries(queryClient)"| RQ
```

Three layers, each with one job:

**`lib/api/client.ts`** is the only module that talks HTTP: an
[openapi-fetch](https://openapi-ts.dev/openapi-fetch/) client typed by the generated
`schema.d.ts` (§4), holding the base URL and `credentials: "include"`. Its one middleware
throws an `ErrorInfo` (an `Error` carrying `status`, message taken from the `detail` field)
for every non-2xx response, so a call that returns has its `data`, hence the `data!`.

**`lib/api/{resource}.ts`** — `devices`, `jobs`, `bookings`, `projects`, `tokens`,
`requests`, `notices`, `admin-control`, `auth` — export, for each read, a react-query
`queryOptions`: a constant where it takes no argument (`devicesQuery`, `myProjectsQuery`),
else a `get…Query(...)` function (`getMyJobsQuery`, `getNoticesQuery`). For each write they
export an async action function (`createAppToken`, `approveMyRequest`, `switchBackendOff`,
`dismissNotice`, …), plus one-line `refresh*Queries` helpers that invalidate the right keys
after a mutation. Each calls the client with a path and parameters that `tsc` checks against
MSS's schema; where a read takes the whole of an endpoint's query, its argument is typed as
that query (`getNoticesQuery`).

Query keys are `[resource, ...discriminators]`. Every query polls at the `QueryClient`'s
default `refetchInterval`, set in `lib/query-client.ts` from `VITE_REFETCH_INTERVAL_MS` (default 2 min),
which is why the e2e config drops it to 1 s; a query that must not poll says
`refetchInterval: false`.

**Route loaders.** Every route in `router.tsx` has `loader: xLoader(queryClient)`; a loader
that needs app state reads `useAppStore.getState()`.
The loader is exported from the page module next to the component (with an
`// eslint-disable-next-line react-refresh/only-export-components`), pre-fetches through
`queryClient.ensureQueryData(...)` — independent fetches together in one `Promise.all` — and
returns a single typed `XData` object of data, never of query options. The page reads
it with `useLoaderData() as XData` and uses those values as the `default` for its `useQuery`
calls — so the first paint has real data and no loading state, and react-query takes over
afterwards for polling and invalidation.

Every loader is wrapped in `loadOrRedirectIfAuthErr` (`lib/loaders.ts`), which catches a 401/403
from any of the pre-fetches and redirects to `/login`. That is the whole auth guard — there is
no separate `<RequireAuth>` component. Non-fatal per-item fetches use `tryQueryFetchMany`,
which swallows the failure of one item rather than failing the page (used for per-backend
bookings, where one offline backend must not blank the home page).

**Mutations** are `useMutation({ mutationFn: <action from lib/api>, onSuccess: refresh… })`.

**Every request goes through a react-query construct** — `useQuery` / `ensureQueryData` for
reads, `useMutation` for writes. Never `await` an API action straight from an event
handler, and never fetch from a `useEffect`. The hooks are not ceremony: `isPending` is what
disables a submit button, `error` is what a form reports, `onSuccess` is the one place the
`refresh*Queries` invalidation belongs, and the shared cache is how a write on one page
updates a table on another. A hand-rolled `try`/`catch` gets none of that and leaves the
rest of the app looking at stale data. Feedback after a write is a `toast` from
`hooks/use-toast`.

**Navigation goes through react-router** — `<Link>` / `<NavLink>` to move, `useNavigate` for
a redirect from code, `redirect()` from a loader, and the route itself for state that belongs
in the URL. Never `window.location`, `history.pushState`, or a bare `<a href>` to an internal
route: they reload the bundle and throw away the query cache and app state. `login.tsx` uses
`window.location.origin` to build the OAuth `next` parameter — that is a URL being *sent to
the provider*, not navigation, and it is the only such use.

### Global state

Deliberately tiny. The zustand store `useAppStore` (`lib/app-state.ts`) holds only what is
neither server data nor URL state:

- `currentProjectId` / `setCurrentProjectId` — the project selected in the topbar,
  which scopes jobs and tokens across pages
- `apiToken` / `setApiToken` — a freshly minted token, held long enough to show it once
- `isDark` / `toggleIsDark` — the theme, the one field its `persist` middleware keeps in
  localStorage; the API token must never reach storage
- `clear()` — used on logout

Components read it with the hook (`useAppStore((state) => state.isDark)`), loaders with
`useAppStore.getState()`. The router is built once, in `app.tsx`, and
`revalidateOnProjectChange` reruns the loaders when the selected project changes. Everything
else is either in the react-query cache (server state) or in the route (which device, which
page). Do not add server data to the store.

### Routes

`public/` holds the assets copied verbatim into the bundle, including two **static** pages
outside React entirely — `privacy.html` and `terms.html`, linked from the footer and covered
by their own Playwright specs. `index.html` is the vite entry that mounts `#root`.

`/` is the `Dashboard` layout with `dashboardLoader` (fetches the current user, derives
`isUserAdmin`); its children are `/` (home), `/devices`, `/devices/:deviceName`, `/tokens`,
`/projects`, `/requests`, `/admin-projects`, `/admin-requests`, `/admin-control`. `/login` sits outside the
layout. An `ErrorBoundary` around the layout's `<Outlet/>`, reset on navigation, and one around
the login page catch render errors; the layout and the child group each have an
`errorElement` of `<ErrorAlert>` for loader errors. Either way a failure inside a page
replaces the page rather than the whole app.

## 3. UI conventions

- **Tailwind + shadcn/ui**, `style: new-york`, base colour gray, CSS variables. Colours are
  never literal — use the semantic tokens (`bg-background`, `text-muted-foreground`,
  `border-input`, `bg-destructive`) defined in `tailwind.config.js` against the custom
  properties in `src/index.css`. Dark mode is the `dark` class on the layout root, driven by
  the store's `isDark`.
- **Add a shadcn primitive** with the shadcn CLI (config in `components.json`) so it lands in
  `src/components/ui/` with the project's style, then edit it in place — these are vendored
  source files, not a dependency.
- **`cn()`** from `lib/utils.ts` (clsx + tailwind-merge) for every conditional class list.
- **Forms** are `react-hook-form` + `zod` via `@hookform/resolvers`, rendered through the
  `Form`/`FormField`/`FormItem`/`FormMessage` primitives. Define the schema as a
  module-level `const formSchema = z.object({...})` and type the form with
  `z.infer<typeof formSchema>`.
- **Charts** are `@visx/*` (`donut-chart.tsx`, `calibration-bar-chart/`,
  `calibration-map-chart.tsx`); calendars are `@fullcalendar/*` wrapped by
  `ui/event-calendar.tsx`. Dates and durations are `luxon` (`DateTime`) — prefer it over
  `Date` arithmetic; `date-fns` is present only for `react-day-picker`.
- **Icons** are `lucide-react`.
- **e2e hooks**: give anything a test needs to find a stable `id` (`id="jobs-table"`) or a
  `data-cy-*` attribute (`data-cy-login-link`). Test selectors must not depend on
  Tailwind classes or DOM position.

## 4. Types

The API contract is generated: `npm run generate:api` runs MSS's `dev/openapi/export.py`,
which writes `apps/tergite-mss/dev/openapi/openapi.json`, and `openapi-typescript` turns that
into `src/lib/api/schema.d.ts`. Never edit the generated file; rerun the command. CI runs
`npm run check:api`, which fails when `schema.d.ts` is stale. The client's paths, parameters,
bodies and responses come from it, so a change to an MSS route or DTO fails `tsc` here.

The components still use the hand-written types in the top-level [types.ts](./types.ts),
which the mock API server and the Playwright specs import too (`Device`, `Job`, `Project`,
`AppToken`, `UserRequest`, `Booking`, `Notice`, `User`, the `JobStatus` / `UserRole` /
`NoticeSeverity` enums, …); the `lib/api` modules cast the client's data to them.

Component-local prop types stay in the component file, conventionally as
`interface Props { … }` **below** the component that uses them, matching the existing files.
Loader payload types follow the same placement as `interface XData`.

`tsconfig.json` is `strict` with `noUnusedLocals` and `noUnusedParameters`, so an
intentionally unused binding must be `_`-prefixed (the eslint rule matches). `@/*` resolves
to `src/*` in both tsconfig and vite; imports of `types.ts` from within `src` are relative.

## 5. The mock API server (`dev/mock-api/`)

An Express app that impersonates MSS well enough to develop and test the UI without running
the real stack.

```
dev/mock-api/
├── server.ts        # express setup, mounts routers, JSON error handler ({ detail })
├── routes/
│   ├── general.ts   # every MSS resource endpoint, plus GET /refreshed-db
│   └── oauth.ts     # the mock OAuth2 authorize/callback pair
├── views/oauth.hbs  # the fake provider's consent page
└── utils.ts         # MockDb over the fixtures in fixtures + JWT signing/verification
```

- `utils.ts` builds an in-memory `MockDb` from `fixtures/*.json` and issues real
  HS256 JWTs with `jose`, using `JWT_SECRET` / `AUTH_AUDIENCE` from the `.env` file — so the
  cookie handling under test is the real thing, not a stub.
- `GET /refreshed-db` resets the mock database; the Playwright fixtures call it between tests.
- `CURRENT_DATE` in `.env.test` pins "now" so date-sensitive fixtures and visual snapshots
  are stable.

Run it with `npm run dev-api` (watch mode) or `npm run test-api`. `npm run dev` starts it and
vite together via `start-server-and-test`.

**When an MSS response shape changes**, rerun `npm run generate:api`, then update
`types.ts`, the mock route in `dev/mock-api/routes/general.ts`, and the fixture in `fixtures/`. Missing one shows
up as a passing UI suite against a stale contract — which is what the repo-level
`dev/e2e_native_test.sh` exists to catch.

## 6. Testing

| Suite | Runner | Scope |
| --- | --- | --- |
| Component | vitest + happy-dom + Testing Library | files matching `src/**/__tests__/*` only |
| e2e | Playwright against vite preview, each worker with its own mock API | `playwright/*.spec.ts`, one spec per page |
| Visual | Playwright's `toHaveScreenshot` inside the e2e run | baselines in `playwright/*-snapshots/`, one set per platform |

```bash
npm run test    # component tests
npm run e2e     # build --mode test, serve, run playwright on parallel workers
npm run visual-e2e   # same, in playwright's UI mode
```

Each Playwright worker starts its own mock API on `PW_API_PORT_BASE` (8100) plus its index, and
`playwright/fixtures.ts` redirects the page's requests for the build's API address to it, so
workers never share data. Runs at the same time need different `PW_API_PORT_BASE`s. With
`DASHBOARD_URL` set, as [dev/e2e_native_test.sh](../../dev/e2e_native_test.sh) sets it, the same specs test
that dashboard on one worker against its stack's API instead.

Each feature's happy path, and the spec that walks it:

| Feature | Spec |
| --- | --- |
| Login | `login.spec.ts` |
| Layout: sidebar, top bar, project switch, app token | `dashboard.spec.ts` |
| Home: devices, jobs, bookings | `home.spec.ts` |
| Devices | `devices.spec.ts` |
| Device detail, bookings and calibrations | `device-detail.spec.ts` |
| Projects, QPU-time and access requests | `projects.spec.ts` |
| Tokens | `tokens.spec.ts` |
| My requests | `my-requests.spec.ts` |
| Approvals | `approvals.spec.ts` |
| Notices | `notices.spec.ts` |
| Settings | `settings.spec.ts` |
| Admin projects | `admin-projects.spec.ts` |
| Admin requests | `admin-requests.spec.ts` |
| Admin control | `admin-control.spec.ts` |
| Error page | `error-alert.spec.ts` |

Job submission has no UI; its happy path is the MSS pytest flow in `tests/api/test_jobs.py`.

Component tests are the thin layer: `vite.config.ts` restricts them to `__tests__`
directories, and only pure-ish primitives are covered there (`ui/__tests__/donut-chart.test.tsx`).
The real coverage is the Playwright suite, which drives the app through the mock API. Each
spec names the fixture users whose roles or data change its pages, and runs its tests for
each (`for (const user of users)`). The `resetData` fixture resets a worker's data before a
test only if an earlier test wrote, so read-only tests share a reset. The browser runs in
`Europe/Stockholm`, the config's `timezoneId` — a change of zone will move snapshots.

Playwright names visual baselines after the platform, so CI needs the linux ones. Generate
them in Playwright's linux image through `Dockerfile.playwright`; see the "How to Generate
Snapshots for CI" section of [CONTRIBUTING.md](./CONTRIBUTING.md).

## 7. Build and serve

`npm run build` = `tsc` (type-check only, `noEmit`) then `vite build` → `dist/`. Because
`VITE_*` variables are inlined at build time, **a different API URL means a different
build**. Every mode's base is `/ui/`, where MSS serves the build, and the router takes it as its
basename; the production build's empty `VITE_API_BASE_URL` calls MSS's own origin.

`npm run lint` is eslint with `--max-warnings 0`, extending
`@typescript-eslint/recommended`, `react-hooks/recommended` and `react-refresh`. It is a CI
gate, so keep the `react-refresh/only-export-components` disables minimal and only where a
loader, or a constant other files share (`SEVERITY_LABELS` in `ui/notice-banner.tsx`), must be
exported alongside a component.

## 8. Adding things — where to start

| Task | Path |
| --- | --- |
| New page | `src/pages/{name}/index.tsx` exporting the component **and** its `loader`; add the `<Route>` in `src/router.tsx`; add a nav item in `layouts/dashboard/components/sidebar.tsx` **and** `topbar/mobile-menu.tsx`, which mirror each other — unless it is only reached in context, as `/approvals` and `/settings` are |
| New component used by one page | `src/pages/{page}/components/` — a file if it is a leaf, a folder with `index.tsx` if it has children |
| New component used by two+ pages | promote to `src/components/ui/` and strip any page knowledge |
| New table | a `*-table/` folder with `index.tsx`, `columns.tsx`, `filter-form.tsx` (+ `detail-drawer.tsx`) |
| New API call | a `queryOptions` (reads) or an action function (writes) in its resource's `src/lib/api/{resource}.ts`, calling `client` from `src/lib/api/client.ts` — nowhere else talks HTTP — then consume it from a `useQuery` or a `useMutation`, never from a bare handler; if MSS gained the route, `npm run generate:api` first |
| New destination | a `<Route>` in `src/router.tsx` with its loader; reach it with `<Link>` or `useNavigate`, never `window.location` |
| New response shape | `npm run generate:api`, then `types.ts`, the mock route in `dev/mock-api/routes/general.ts`, and the `fixtures/` JSON |
| New shadcn primitive | the shadcn CLI, then edit the generated file in `src/components/ui/` |
| New env variable | `VITE_`-prefix it if the browser needs it, and add it to `.env.development` / `.env.test`, and to `.env.production` if the build MSS serves needs a value |
