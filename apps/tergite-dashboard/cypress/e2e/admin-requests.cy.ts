/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import userList from "../fixtures/users.json";
import projectList from "../fixtures/projects.json";
import userRequestList from "../fixtures/user-requests.json";
import { generateJwt, getUsername } from "../../api/utils";
import { getUserRequestDetails } from "../support/utils";
import {
  type UserRequest,
  type Project,
  type User,
  UserRole,
  UserRequestStatus,
  UserRequestType,
} from "../../types";

const projects = [...projectList] as Project[];
const projectsIndex = Object.fromEntries(projects.map((v, i) => [v.id, i]));
const userRequests = [...userRequestList] as UserRequest[];
const users = [...userList] as User[];

const requestsTableHeaders = [
  "Title",
  "Type",
  "Requested by",
  "Created",
  "Status",
  "",
];
const requestsTableDataProps = [
  "title",
  "type",
  "requester_name",
  "created_at",
  "status",
  "actions",
];

users.forEach((user) => {
  const isAdmin = user.roles.includes(UserRole.ADMIN);
  const username = getUsername(user);
  // the page lists the pending requests awaiting this user's decision, newest first
  const pendingUserRequests = userRequests
    .filter(
      (v) =>
        v.status === UserRequestStatus.PENDING &&
        v.target_user_ids.includes(user.id)
    )
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const qpuTimeRequests = pendingUserRequests.filter(
    (v) => v.type === UserRequestType.PROJECT_QPU_SECONDS
  );

  describe(`admin user requests page for ${username}`, () => {
    const dashboardUrl = Cypress.config("baseUrl");

    beforeEach(() => {
      const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
      const dbResetUrl = Cypress.env("DB_RESET_URL");
      const domain = Cypress.env("VITE_COOKIE_DOMAIN");
      const cookieName = Cypress.env("VITE_COOKIE_NAME");
      const secret = Cypress.env("JWT_SECRET");
      const audience = Cypress.env("AUTH_AUDIENCE");
      const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

      cy.intercept("GET", `${apiBaseUrl}/devices/*`).as("devices-list");
      cy.intercept("GET", `${apiBaseUrl}/me/projects/?is_active=true`).as(
        "my-active-project-list"
      );
      cy.intercept("GET", `${apiBaseUrl}/me/projects/?*`).as("my-project-list");
      cy.intercept("GET", `${apiBaseUrl}/me/profile`).as("my-user-info");
      cy.intercept("GET", `${apiBaseUrl}/me/requests/?*`).as(
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

      // We need to reset the mongo database before each test
      cy.request(`${dbResetUrl}`);
      cy.wait(500);

      cy.visit("/admin-requests");
      cy.wait("@my-user-info");
      cy.wait("@my-active-project-list");
      isAdmin && cy.wait("@user-requests-list");
    });

    isAdmin &&
      it("renders number of pending requests", () => {
        cy.visit("/");
        cy.wait("@my-user-info");
        cy.url().should("equal", dashboardUrl);

        cy.get("[data-testid='sidebar'] a[href='/admin-requests']").within(() => {
          cy.contains(".bg-primary", `${pendingUserRequests.length}`);
        });
      });

    isAdmin &&
      it("does not render number of pending requests when sidebar is collapsed", () => {
        cy.visit("/");
        cy.wait("@my-user-info");
        cy.url().should("equal", dashboardUrl);

        cy.get("[data-testid='sidebar'] [aria-label='PanelLeftClose']")
          .parent()
          .click();

        cy.get("[data-testid='sidebar'] a[href='/admin-requests']").within(() => {
          cy.contains(".bg-primary", `${pendingUserRequests.length}`).should(
            "not.exist"
          );
        });
      });

    isAdmin &&
      it("renders the admin requests page when nav item is clicked", () => {
        cy.visit("/");
        cy.wait("@my-user-info");
        cy.url().should("equal", dashboardUrl);

        cy.get("[data-testid='sidebar'] a[href='/admin-requests']").click();
        cy.url().should("equal", `${dashboardUrl}admin-requests`);
      });

    !isAdmin &&
      it("requests link in sidebar does not exist", () => {
        cy.visit("/");
        cy.wait("@my-user-info");
        cy.url().should("equal", dashboardUrl);

        cy.get("[data-testid='sidebar'] a[href='/admin-requests']").should(
          "not.exist"
        );
      });

    !isAdmin &&
      it("redirects to home when admin-requests URL is visited", () => {
        cy.url().should("equal", dashboardUrl);
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
                          } else if (prop === "actions") {
                            // every row here is pending, so both quick
                            // responses are offered
                            expect(cell.td.text()).to.match(
                              /approve\s*reject/i
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
      it("filters the list of user requests", () => {
        const filterMaps = [
          {
            input: { title: "close" },
            result: pendingUserRequests.filter((v) =>
              /close/i.test(getTitle(v))
            ),
          },
          {
            input: {
              title: "test 2",
              type: UserRequestType.PROJECT_QPU_SECONDS,
            },
            result: pendingUserRequests.filter(
              (v) =>
                /test 2/i.test(getTitle(v)) &&
                v.type == UserRequestType.PROJECT_QPU_SECONDS
            ),
          },
          {
            input: { requester_name: "pa" },
            result: pendingUserRequests.filter((v) =>
              /pa/i.test(v.requester_name ?? "")
            ),
          },
          {
            input: { status: UserRequestStatus.REJECTED },
            result: pendingUserRequests.filter(
              (v) => v.status === UserRequestStatus.REJECTED
            ),
          },
          {
            input: { type: UserRequestType.CLOSE_PROJECT },
            result: pendingUserRequests.filter(
              (v) => v.type === UserRequestType.CLOSE_PROJECT
            ),
          },
          {
            input: {
              title: "test",
              requester_name: "j",
              status: UserRequestStatus.PENDING,
              type: UserRequestType.PROJECT_QPU_SECONDS,
            },
            result: pendingUserRequests.filter(
              (v) =>
                /test/i.test(getTitle(v)) &&
                v.status === UserRequestStatus.PENDING &&
                /j/i.test(v.requester_name ?? "") &&
                v.type == UserRequestType.PROJECT_QPU_SECONDS
            ),
          },
        ];

        cy.viewport(1728, 1117);
        cy.get(".bg-card table").as("request-list-table");
        cy.get(".bg-card [aria-label='Filter']").as("filterBtn");

        cy.get("@filterBtn")
          .click()
          .then(() => {
            cy.get("[data-cy-filter-form] input[name='title']").as(
              "titleInput"
            );
            cy.get("[data-cy-filter-form] input[name='requester_name']").as(
              "requesterNameInput"
            );
            cy.get("[data-cy-filter-form] #request-type-select").as(
              "typeSelect"
            );
            cy.get("[data-cy-filter-form] #request-status-select").as(
              "statusSelect"
            );

            cy.get("[data-cy-filter-form] button[type='submit']").as(
              "submitBtn"
            );
            cy.get("[data-cy-filter-form] button[type='reset']").as("clearBtn");

            for (const filterMap of filterMaps) {
              cy.wrap(filterMap).then(({ input, result }) => {
                input.title && cy.get("@titleInput").type(input.title);
                input.requester_name &&
                  cy.get("@requesterNameInput").type(input.requester_name);
                input.type &&
                  cy
                    .get("@typeSelect")
                    .click()
                    .then(() => {
                      cy.get("[data-cy-user-request-type-select]").within(
                        () => {
                          cy.contains(input.type).click();
                        }
                      );
                    });
                input.status &&
                  cy
                    .get("@statusSelect")
                    .click()
                    .then(() => {
                      cy.get("[data-cy-user-request-status-select]").within(
                        () => {
                          cy.contains(new RegExp(input.status, "i")).click();
                        }
                      );
                    });
                cy.get("@submitBtn")
                  .click()
                  .then(() => {
                    cy.get("@request-list-table")
                      .find("tbody tr")
                      .should("have.length", result.length || 1);

                    for (const request of result) {
                      cy.wrap(request).then((request) => {
                        cy.get("@request-list-table").within(() =>
                          cy
                            .get("tr td:first-child")
                            .contains(getTitle(request))
                            .should("be.visible")
                        );
                      });
                    }

                    cy.get("@clearBtn")
                      .click()
                      .then(() => {
                        cy.get("@request-list-table")
                          .find("tbody tr")
                          .should(
                            "have.length",
                            pendingUserRequests.length || 1
                          );

                        for (const request of pendingUserRequests) {
                          cy.wrap(request).then((request) => {
                            cy.get("@request-list-table").within(() =>
                              cy
                                .get("tr td:first-child")
                                .contains(getTitle(request))
                                .should("be.visible")
                            );
                          });
                        }
                      });
                  });
              });
            }
          });
      });

    isAdmin &&
      it("renders sidebar placeholder by default", () => {
        cy.viewport(1080, 750);
        // request summary should not exist
        cy.get("#request-summary").should("not.exist");
        cy.contains("#sidebar-placeholder h3", /user request title/i).should(
          "be.visible"
        );
        cy.contains(
          "#sidebar-placeholder .font-semibold",
          /request details/i
        ).should("be.visible");
        cy.contains(
          "#sidebar-placeholder .text-muted-foreground",
          /click any row to show details here/i
        ).should("be.visible");
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
              const requestBody = getUserRequestDetails(request);

              cy.wrap(obj.el).realClick();

              // sidebar placeholder should not exist
              cy.get("#sidebar-placeholder").should("not.exist");

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
      it("approves straight from the row, without opening the request", () => {
        cy.viewport(1080, 750);
        cy.wait("@user-requests-list");

        const title = getTitle(qpuTimeRequests[0]);
        cy.contains(".bg-card tbody tr", title).within(() => {
          cy.get("[data-cy-row-approve]").click();
        });

        cy.wait("@user-requests-list");
        // the table lists only pending requests, so an approved one drops out
        cy.contains(".bg-card tbody td", title).should("not.exist");
        // and the row click never fired, so no detail panel opened
        cy.get("#request-summary").should("not.exist");
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
            const projectId = obj.request.resource_id;
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
              obj.request.metadata.seconds ?? 0;

            // sidebar shows correct number
            cy.get("[data-testid='sidebar'] a[href='/admin-requests']").within(
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
            const projectId = obj.request.resource_id;
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
            cy.get("[data-testid='sidebar'] a[href='/admin-requests']").within(
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
  // an admin sees every project, so knows the name of the one requested on
  const project = projects[projectsIndex[userRequest.resource_id]];
  const projectName = project?.name ?? userRequest.resource_id;
  return {
    [UserRequestType.CLOSE_PROJECT]: `Close project '${projectName}'`,
    [UserRequestType.CREATE_PROJECT]: `Create new project '${userRequest.metadata.name}'`,
    [UserRequestType.PROJECT_QPU_SECONDS]: `Add QPU time on project: '${projectName}'`,
    [UserRequestType.TRANSFER_PROJECT]: `Transfer project '${projectName}'`,
    [UserRequestType.PROJECT_ACCESS]: `Join project '${projectName}'`,
  }[userRequest.type];
}
