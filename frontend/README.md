# Frontend

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 21.1.1.

## Development server

To start a local development server, run:

```bash
ng serve
```

Once the server is running, open your browser and navigate to `http://localhost:4200/`. The application will automatically reload whenever you modify any of the source files.

## Login and registration

The `/login` and `/register` pages call the Spring Boot API directly. In development, `src/environments/environment.development.ts` points to `http://localhost:8080/api`; start PostgreSQL and the backend before trying auth.

Registration sends `email`, `fullName`, `password`, and `role`. The role is one of `student`, `instructor` (giáo viên), or `admin`. A successful login or registration stores the returned bearer token and routes to the matching area. The admin area is currently a placeholder page.

`useMock: true` only keeps the practice/course APIs in demo mode; it does not mock login or registration. For production, configure the web server to proxy `/api` to Spring Boot, matching `src/environments/environment.ts`.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Vitest](https://vitest.dev/) test runner, use the following command:

```bash
ng test
```

## Running end-to-end tests

For end-to-end (e2e) testing, run:

```bash
ng e2e
```

Angular CLI does not come with an end-to-end testing framework by default. You can choose one that suits your needs.

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.
