import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let backend: HttpTestingController; // a fake server: we decide what it answers
  let auth: AuthService;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'login', children: [] }]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  it('adds the Bearer token to every request', () => {
    auth.token.set('abc123');
    void firstValueFrom(http.get('/api/leave-requests'));
    const req = backend.expectOne('/api/leave-requests');
    expect(req.request.headers.get('Authorization')).toBe('Bearer abc123');
    req.flush({});
  });

  it('logs out when the API answers 401', async () => {
    auth.token.set('expired');
    const call = firstValueFrom(http.get('/api/auth/me')).catch(() => 'failed');
    backend.expectOne('/api/auth/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(await call).toBe('failed');
    expect(auth.isLoggedIn()).toBe(false);
  });
});
