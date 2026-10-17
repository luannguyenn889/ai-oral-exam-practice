import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';

import { routes } from './app.routes';
import { environment } from '../environments/environment';
import { PracticeApi } from './data-access/api/practice.api';
import { MockPracticeApi } from './data-access/mock/mock-practice.api';
import { HttpPracticeApi } from './data-access/api/http-practice.api';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(),
    provideAnimationsAsync(),
    // Chọn Mock hay HTTP API dựa theo environment.useMock (Giai đoạn A)
    {
      provide: PracticeApi,
      useClass: environment.useMock ? MockPracticeApi : HttpPracticeApi,
    },
  ],
};
