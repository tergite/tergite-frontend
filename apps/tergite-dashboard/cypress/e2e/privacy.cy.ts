describe("Loads the privacy policy page", () => {
  it("should display the privacy policy content", () => {
    cy.visit("/privacy.html");
    cy.contains("Privacy Policy");
  });
});