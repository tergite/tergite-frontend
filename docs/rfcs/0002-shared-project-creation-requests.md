# RFC 0002 — Shared project creation requests

| | |
| --- | --- |
| **Status** | Skeleton — not ready for review |
| **Scope** | `apps/tergite-mss`, `apps/tergite-dashboard` |
| **Depends on** | [RFC 0001](./0001-project-access-requests-and-notifications.md) phases 1–3 |
| **Created** | 2026-08-18 |

> This is a placeholder capturing the problem, the constraints already discovered, and the
> questions that need answering. It is not a design yet. Fill it in once RFC 0001's request and
> notification machinery exists, because most of this RFC is "add one type to that frame".

## 1. Problem

A group forming around a new grant or collaboration needs a **shared** project that does not exist
yet. Today the only way is emailing a superuser, who creates it by hand through
`POST /admin/projects/` (the `CreateProjectForm` on the admin-projects page).

RFC 0001 deliberately does not cover this. Its three mechanisms are:

| Need | Mechanism |
| --- | --- |
| A starter project to experiment in | auto-created personal project |
| Join a shared project that already exists | `project-access` request |
| **Bring a new shared project into being** | **this RFC** |

## 2. What already exists

The `create-project` `UserRequestType` was declared for exactly this and never wired up — see
RFC 0001 §4.1 for the full inventory. It is reserved, not dead-by-accident:

- `UserRequestType.CREATE_PROJECT` in `services/auth/user_requests/dtos.py`.
- `CreateProjectPostBody` and `CreateProjectUserRequest` in the dashboard's `types.ts`, and a
  `case "create-project"` in `getUserRequestTitle`.
- One padding row in each of the two `user_requests` fixtures.
- **No producer and no approval side effect.** `user_requests.update()` branches only on
  `PROJECT_QPU_SECONDS`, so an approved `create-project` request would silently create nothing.

After RFC 0001 the following are also in place and should be reused rather than reinvented:
`approver_scope`, the `/me/requests/` endpoints, the eligibility rule including the
never-approve-your-own clause, the notification service and its type/channel metadata, and the
`/approvals` page structure.

## 3. Constraints already known

- **`approver_scope = SYSTEM_ADMIN`.** A project that does not exist has no project admin, so
  there is no one else it could route to.
- **`Project.ext_id` is uniquely indexed.** A user-chosen `ext_id` can collide, including with a
  *pending* request nobody has approved yet — so uniqueness has to be checked twice, or reserved
  at request time.
- **Do not touch `CreateProjectPostBody`.** Despite the name it is load-bearing: `Project` is
  `Omit<CreateProjectPostBody, "user_emails">`, `UpdateProjectPutBody` is
  `Partial<Omit<CreateProjectPostBody, "ext_id">>`, and `AdminCreateProjectBody` extends it.
  Renaming it to reflect what it actually is would be an improvement, but it is a rename with a
  wide blast radius, not a deletion.
- **`_get_user_email_id_map` creates users for unknown emails.** Listing member emails on a project
  silently provisions stub user accounts (via `User.insert_many`, bypassing `UserManager`). An
  approved creation request would inherit that behaviour, which means a requester could cause
  account creation for arbitrary addresses. Needs a deliberate decision, not an inherited one.
- **The requester should become the project admin**, presumably — but they are not a superuser, so
  this is the first case of a non-superuser gaining admin rights over a project through a request.

## 4. Questions to answer

1. **Who chooses `ext_id`?** Requester-supplied risks collisions and squatting on meaningful ids;
   generated is safe but shared projects are referred to by id in conversation and grant paperwork,
   so a meaningful one has real value. A third option: requester proposes, approver can amend.
2. **May the approver amend the payload before approving?** Adjusting a requested allowance from
   10 000 to 1 000 seconds is the obvious case. This is the biggest structural question — an
   amendable request needs a different `PUT` shape than the boolean approve/reject of RFC 0001, and
   it changes the `/approvals` UI from two buttons to a form.
3. **What allowance may a requester ask for, and what is granted?** Requested vs granted are
   probably different fields. Does a configured cap apply?
4. **Who are the initial members?** Emails, as `AdminCreateProjectBody` does — and if so, what
   happens to the stub-user-creation behaviour above? Or admin-only at creation, with everyone else
   arriving through RFC 0001's `project-access` requests?
5. **Does the requester become the project admin automatically?**
6. **Is there a cap on pending creation requests per user?** RFC 0001's
   `max_pending_requests_per_user` may already cover it.
7. **Does an approved-then-deleted project's `ext_id` become reusable?** Deleted projects are
   archived to `deleted_auth_projects`, which still holds the `ext_id`.

## 5. Sketch of the shape

Enough to see it is small once RFC 0001 lands. Not a commitment.

- `CreateProjectPostBody` on the MSS side (new, distinct from the dashboard type of the same name):
  `name`, `ext_id?`, `description?`, `user_emails?`, `requested_qpu_seconds`, `reason`.
- `POST /me/requests/` with `type = create-project`, `approver_scope = SYSTEM_ADMIN`.
- Approval side effect in `user_requests.update()`: build a `Project` and go through
  `ProjectAppTokenManager.create`, which already raises `ProjectExists` on a duplicate `ext_id` —
  so the collision path is a 409 on approval, unless question 1 resolves to generated ids.
- Notification types `PROJECT_CREATION_REQUESTED` / `_APPROVED` / `_REJECTED`, added to
  `NOTIFICATION_TYPE_META` and `CHANNEL_POLICY`.
- Dashboard: a request dialog next to RFC 0001's request-access dialog on `pages/projects/`, and
  the type appearing in `/approvals` for superusers. `getUserRequestTitle` already handles the
  type.
- Validation: reject a duplicate `ext_id` at request time as well as approval time, and apply the
  §11.1 lookup rate limit if `ext_id` availability is checkable from the form.

## 6. Non-goals (provisional)

- No project **transfer** or **closure** requests. `TRANSFER_PROJECT` and `CLOSE_PROJECT` are also
  declared-but-unwired and would each be their own small RFC on the same frame.
- No hierarchy, quotas per institution, or grant accounting.
