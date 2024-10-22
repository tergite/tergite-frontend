/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import userList from "../fixtures/users.json";
import projectList from "../fixtures/projects.json";
import userRequestList from "../fixtures/user-requests.json";
import { generateJwt, getUsername } from "../../api/utils";
import {
  type UserRequest,
  type Project,
  type User,
  UserRole,
  UserRequestStatus,
  UserRequestType,
  AnyFlatRecord,
  QpuTimeExtensionUserRequest,
} from "../../types";

const projects = [...projectList] as Project[];
const projectsIndex = Object.fromEntries(projects.map((v, i) => [v.id, i]));
const userRequests = [...userRequestList] as UserRequest[];
const pendingUserRequests = userRequests.filter(
  (v) => v.status === UserRequestStatus.PENDING
);
const qpuTimeRequests = pendingUserRequests.filter(
  (v) => v.type === UserRequestType.PROJECT_QPU_SECONDS
) as QpuTimeExtensionUserRequest[];
const users = [...userList] as User[];

const requestsTableHeaders = [
  "Title",
  "Type",
  "Requested by",
  "Created",
  "Status",
];
const requestsTableDataProps = [
  "title",
  "type",
  "requester_name",
  "created_at",
  "status",
];

users.forEach((user) => {
  const isAdmin = user.roles.includes(UserRole.ADMIN);
  const username = getUsername(user);

  describe(`admin user requests page for ${username}`, () => {
    beforeEach(() => {
      const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
      const domain = Cypress.env("VITE_COOKIE_DOMAIN");
      const cookieName = Cypress.env("VITE_COOKIE_NAME");
      const secret = Cypress.env("JWT_SECRET");
      const audience = Cypress.env("AUTH_AUDIENCE");
      const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

      cy.intercept("GET", `${apiBaseUrl}/devices`).as("devices-list");
      cy.intercept("GET", `${apiBaseUrl}/me/projects`).as("my-project-list");
      cy.intercept("GET", `${apiBaseUrl}/me`).as("my-user-info");
      cy.intercept("GET", `${apiBaseUrl}/admin/qpu-time-requests*`).as(
        "my-qpu-requests-list"
      );
      cy.intercept("GET", `${apiBaseUrl}/admin/user-requests*`).as(
        "user-requests-list"
      );

      if (user.id) {
        cy.wrap(generateJwt(user, cookieExpiry, { secret, audience })).then(
          (jwtToken) => {
            cy.setCookie(cookieName, jwtToken as string, {
              domain,
              httpOnly: true,
              secure: false,
              sameSite: "lax",
            });
          }
        );
      }

      cy.request(`${apiBaseUrl}/refreshed-db`);

      cy.visit("/admin-requests");
      cy.wait("@my-user-info");
      cy.wait("@my-project-list");
      isAdmin && cy.wait("@user-requests-list");
    });

    isAdmin &&
      it("renders number of pending requests", () => {
        cy.visit("/");
        cy.wait("@my-user-info");
        cy.url().should("equal", "http://127.0.0.1:5173/");

        cy.contains("[data-testid='sidebar'] div", /requests/i).within(() => {
          cy.contains(".bg-primary", `${pendingUserRequests.length}`);
        });
      });

    isAdmin &&
      it("renders the admin requests page when nav item is clicked", () => {
        cy.visit("/");
        cy.wait("@my-user-info");
        cy.url().should("equal", "http://127.0.0.1:5173/");

        cy.contains("[data-testid='sidebar'] a", /requests/i).click();
        cy.url().should("equal", "http://127.0.0.1:5173/admin-requests");
      });

    !isAdmin &&
      it("requests link in sidebar does not exist", () => {
        cy.visit("/");
        cy.wait("@my-user-info");
        cy.url().should("equal", "http://127.0.0.1:5173/");

        cy.contains("[data-testid='sidebar'] a", /requests/i).should(
          "not.exist"
        );
      });

    !isAdmin &&
      it("redirects to home when admin-requests URL is visited", () => {
        cy.url().should("equal", "http://127.0.0.1:5173/");
      });

    isAdmin &&
      it("renders all pending user requests", () => {
        cy.viewport(1080, 750);
        cy.wait(200);
        cy.contains(".bg-card", /pending user requests/i).within(() => {
          cy.get("table").as("request-list-table");

          // header
          cy.get("@request-list-table")
            .get("thead th")
            .each((el, idx) => {
              expect(el.text()).to.eql(requestsTableHeaders[idx]);
            });

          // body
          cy.get("@request-list-table")
            .get("tbody")
            .within(() => {
              cy.get("tr").each((el, idx) => {
                cy.wrap({ el, idx }).then((obj) => {
                  const request = pendingUserRequests[obj.idx];

                  if (request) {
                    cy.wrap(obj.el).within(() => {
                      cy.get("td").each((td, cellIdx) => {
                        cy.wrap({ td, request, idx: cellIdx }).then((cell) => {
                          const prop = requestsTableDataProps[cell.idx];
                          if (prop === "created_at") {
                            expect(cell.td.text()).to.match(
                              // '1 day ago' or '2 days 2 hours ago'
                              /\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?) ago/i
                            );
                          } else if (prop === "status") {
                            expect(cell.td.text()).to.match(
                              new RegExp(cell.request[prop], "i")
                            );
                          } else if (prop === "title") {
                            expect(cell.td.text()).to.eql(
                              getTitle(cell.request)
                            );
                          } else {
                            expect(cell.td.text()).to.eql(
                              `${cell.request[prop]}`
                            );
                          }
                        });
                      });
                    });
                  } else {
                    cy.wrap(obj.el).within(() => {
                      cy.contains("td", /no results/i).should("be.visible");
                    });
                  }
                });
              });
            });
        });
      });

    isAdmin &&
      it("renders user request summary when row is clicked", () => {
        cy.viewport(1080, 750);
        cy.wait(100);
        cy.get(".bg-card tbody tr").each((el, idx) => {
          cy.wrap({ el, idx }).then((obj) => {
            const request = pendingUserRequests[obj.idx];

            if (request) {
              const requestTitle = getTitle(request);
              const requestBody = request.request as AnyFlatRecord;

              cy.wrap(obj.el).realClick();

              cy.contains("#request-summary h3", requestTitle).should(
                "be.visible"
              );

              // Shows all the details in the request body
              cy.contains(
                "#request-summary [data-cy-request-body] .font-semibold",
                /^request$/i
              ).should("be.visible");
              for (const [reqProp, reqValue] of Object.entries(requestBody)) {
                const label = reqProp.replace(/-|_/g, " ");
                const value = Array.isArray(reqValue)
                  ? reqValue.join(", ")
                  : `${reqValue}`;
                cy.contains(
                  "#request-summary [data-cy-request-body] div",
                  new RegExp(label, "i")
                ).within(() => {
                  cy.contains(value).should("be.visible");
                });
              }

              // Shows the additional metadata about the request
              cy.contains(
                "#request-summary [data-cy-additional-information] .font-semibold",
                /^additional information$/i
              ).should("be.visible");

              cy.contains(
                "#request-summary [data-cy-additional-information] div",
                /requested by/i
              ).within(() => {
                cy.contains(request.requester_name as string).should(
                  "be.visible"
                );
              });

              cy.contains(
                "#request-summary [data-cy-additional-information] div",
                /status/i
              ).within(() => {
                cy.contains(request.status).should("be.visible");
              });

              cy.contains(
                "#request-summary [data-cy-additional-information] div",
                /created/i
              ).within(() => {
                cy.contains(
                  /(\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?),?)+( ago)?/i
                ).should("be.visible");
              });

              cy.contains("#request-summary button", /approve/i).should(
                "be.visible"
              );

              cy.contains("#request-summary button", /reject/i).should(
                "be.visible"
              );
            }
          });
        });
      });

    isAdmin &&
      it("approving a QPU time request increases project QPU time and removes request from pending list", () => {
        cy.viewport(1080, 750);
        const projectsMap = Object.fromEntries(
          projects.map((v) => [v.id, { ...v }])
        );
        const counts = { pending: pendingUserRequests.length };

        for (const request of qpuTimeRequests) {
          cy.wrap({ request, projectsMap, counts }).then((obj) => {
            const projectId = obj.request.request.project_id;
            const project = obj.projectsMap[projectId];
            const projectIdx = projectsIndex[projectId];
            const isProjectMember = project.user_ids.includes(user.id);

            // visit projects page if user is project member
            if (isProjectMember) {
              cy.visit("/projects");
              cy.wait("@my-project-list");

              cy.contains(
                `.bg-card tbody tr[data-id='${projectIdx}'] td[data-header='qpu_seconds']`,
                new RegExp(
                  `${obj.projectsMap[projectId].qpu_seconds} seconds`,
                  "i"
                )
              ).should("be.visible");
            }

            // visit requests page
            cy.visit("/admin-requests");
            cy.wait("@user-requests-list");

            const reqTitle = getTitle(obj.request);
            cy.contains(".bg-card tbody tr", reqTitle).click();

            cy.contains("#request-summary h3", reqTitle).should("be.visible");
            cy.contains(".bg-card tbody td", reqTitle).should("be.visible");

            cy.contains("#request-summary button", /approve/i).realClick();

            cy.contains(".bg-card tbody td", reqTitle).should("not.exist");
            cy.get("#request-summary").should("not.exist");

            // update data
            obj.counts.pending -= 1;
            obj.projectsMap[projectId].qpu_seconds +=
              obj.request.request.seconds;

            // sidebar shows correct number
            cy.contains("[data-testid='sidebar'] div", /requests/i).within(
              () => {
                cy.contains(".bg-primary", `${obj.counts.pending}`);
              }
            );

            // visit projects page again if user is project member; QPU seconds is incremented
            if (isProjectMember) {
              cy.visit("/projects");
              cy.wait("@my-project-list");

              cy.contains(
                `.bg-card tbody tr[data-id='${projectIdx}'] td[data-header='qpu_seconds']`,
                new RegExp(
                  `${obj.projectsMap[projectId].qpu_seconds} seconds`,
                  "i"
                )
              ).should("be.visible");
            }
          });
        }
      });

    isAdmin &&
      it("rejecting a QPU time request removes request from pending list", () => {
        cy.viewport(1080, 750);
        const projectsMap = Object.fromEntries(
          projects.map((v) => [v.id, { ...v }])
        );
        const counts = { pending: pendingUserRequests.length };

        for (const request of qpuTimeRequests) {
          cy.wrap({ request, projectsMap, counts }).then((obj) => {
            const projectId = obj.request.request.project_id;
            const project = obj.projectsMap[projectId];
            const projectIdx = projectsIndex[projectId];
            const isProjectMember = project.user_ids.includes(user.id);

            // visit projects page if user is project member
            if (isProjectMember) {
              cy.visit("/projects");
              cy.wait("@my-project-list");

              cy.contains(
                `.bg-card tbody tr[data-id='${projectIdx}'] td[data-header='qpu_seconds']`,
                new RegExp(
                  `${obj.projectsMap[projectId].qpu_seconds} seconds`,
                  "i"
                )
              ).should("be.visible");
            }

            // visit requests page
            cy.visit("/admin-requests");
            cy.wait("@user-requests-list");

            const reqTitle = getTitle(obj.request);
            cy.contains(".bg-card tbody tr", reqTitle).click();

            cy.contains("#request-summary h3", reqTitle).should("be.visible");
            cy.contains(".bg-card tbody td", reqTitle).should("be.visible");

            cy.contains("#request-summary button", /reject/i).realClick();

            cy.contains(".bg-card tbody td", reqTitle).should("not.exist");
            cy.get("#request-summary").should("not.exist");

            // update data
            obj.counts.pending -= 1;

            // sidebar shows correct number
            cy.contains("[data-testid='sidebar'] div", /requests/i).within(
              () => {
                cy.contains(".bg-primary", `${obj.counts.pending}`);
              }
            );

            // visit projects page again if user is project member; QPU seconds is unchanged
            if (isProjectMember) {
              cy.visit("/projects");
              cy.wait("@my-project-list");

              cy.contains(
                `.bg-card tbody tr[data-id='${projectIdx}'] td[data-header='qpu_seconds']`,
                new RegExp(
                  `${obj.projectsMap[projectId].qpu_seconds} seconds`,
                  "i"
                )
              ).should("be.visible");
            }
          });
        }
      });
  });
});

/**
 * Generates the title of the user request
 *
 * @param userRequest - the request whose title is to be obtained
 */
function getTitle(userRequest: UserRequest): string {
  const reqBody = userRequest.request as AnyFlatRecord;
  return {
    [UserRequestType.CLOSE_PROJECT]: `Close project '${reqBody.project_name}'`,
    [UserRequestType.CREATE_PROJECT]: `Create new project '${reqBody.name}'`,
    [UserRequestType.PROJECT_QPU_SECONDS]: `Add QPU time on project: '${reqBody.project_name}'`,
    [UserRequestType.TRANSFER_PROJECT]: `Transfer project '${reqBody.project_name}'`,
  }[userRequest.type];
}