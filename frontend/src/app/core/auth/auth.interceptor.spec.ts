import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthService } from './auth.service';
import { csrfInterceptor, sessionExpiryInterceptor } from './auth.interceptor';

describe('authentication interceptors', () => {
  let http: HttpClient;
  let requests: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    document.cookie = 'ara_csrf=token-value; path=/';
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([csrfInterceptor, sessionExpiryInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    requests = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => requests.verify());

  it('adds the double-submit token only to same-origin unsafe requests', () => {
    http.post('/api/assets', {}).subscribe();
    const request = requests.expectOne('/api/assets');
    expect(request.request.headers.get('X-CSRF-Token')).toBe('token-value');
    expect(request.request.withCredentials).toBe(true);
    request.flush({});
  });

  it.each(['//evil.example/api/assets', 'https://evil.example/api/assets'])(
    'does not attach CSRF credentials to %s',
    (url) => {
      http.post(url, {}).subscribe();
      const request = requests.expectOne(url);
      expect(request.request.headers.has('X-CSRF-Token')).toBe(false);
      expect(request.request.withCredentials).toBe(false);
      request.flush({});
    },
  );

  it('returns the UI to an expired state after a same-origin 401', () => {
    http.get('/api/assets').subscribe({ error: () => undefined });
    requests.expectOne('/api/assets').flush('expired', { status: 401, statusText: 'Unauthorized' });

    expect(auth.state()).toBe('expired');
  });
});
