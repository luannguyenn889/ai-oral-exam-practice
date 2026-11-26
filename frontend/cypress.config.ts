import { defineConfig } from 'cypress';

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:4200',
    specPattern: 'cypress/e2e/**/*.cy.ts',
    supportFile: 'cypress/support/e2e.ts',
    viewportWidth: 1280,
    viewportHeight: 800,
    video: false,
    screenshotOnRunFailure: true,
    defaultCommandTimeout: 10000,
    requestTimeout: 15000,
    responseTimeout: 30000,
    env: {
      apiUrl: 'http://localhost:8080/api',
      aiUrl: 'http://localhost:8000',
      live: false,
    },
    expose: {
      apiUrl: 'http://localhost:8080/api',
      aiUrl: 'http://localhost:8000',
      live: false,
    },
  },
});
