describe("Loads the terms of use page", () => {
  it("should display the terms of use content", () => {
    cy.visit("/terms.html");
    cy.contains("Terms of Use");
  });
});