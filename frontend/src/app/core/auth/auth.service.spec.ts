import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { AuthService } from './auth.service';

describe('AuthService', () => {
  let auth: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('stores server-resolved roles from the session response', () => {
    auth.loadSession().subscribe();
    const request = http.expectOne('/auth/session');
    expect(request.request.withCredentials).toBe(true);
    request.flush({
      authenticated: true,
      user: { id: 'user-id', display_name: 'Ada', email: 'ada@example.test' },
      roles: { is_owner: true, group_roles: { 'group-id': 'group_admin' } },
    });

    expect(auth.state()).toBe('authenticated');
    expect(auth.roles()?.is_owner).toBe(true);
  });

  it('moves to an error state when session loading fails', () => {
    auth.loadSession().subscribe();
    http
      .expectOne('/auth/session')
      .flush('unavailable', { status: 503, statusText: 'Unavailable' });

    expect(auth.state()).toBe('error');
  });
});
