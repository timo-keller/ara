import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { routes } from '../../app.routes';
import { AuthService } from './auth.service';
import { authenticatedGuard } from './auth.guard';

describe('authenticatedGuard', () => {
  it('permits an already authenticated session', async () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter(routes)] });
    const auth = TestBed.inject(AuthService);
    auth.state.set('authenticated');

    const result = await TestBed.runInInjectionContext(() =>
      firstValueFrom(
        authenticatedGuard({} as never, {} as never) as ReturnType<typeof auth.ensureSession>,
      ),
    );

    expect(result).toBe(true);
  });
});
