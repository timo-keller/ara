import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { AuthService, type SessionUser } from '../auth/auth.service';
import { NotificationService } from '../notifications/notification.service';
import { CompactModeService } from './compact-mode.service';
import { SettingsComponent } from './settings.component';

describe('SettingsComponent', () => {
  const user = signal<SessionUser | null>(null);

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [
        { provide: AuthService, useValue: { user } },
        {
          provide: CompactModeService,
          useValue: { compact: signal(false), setCompact: () => undefined },
        },
        {
          provide: NotificationService,
          useValue: {
            unreadCount: signal(0),
            notifications: signal([]),
            loading: signal(false),
            error: signal(false),
            browserPermission: signal('unavailable'),
            refresh: () => undefined,
            markAllRead: () => undefined,
            markRead: () => undefined,
            requestBrowserPermission: () => undefined,
          },
        },
      ],
    }).compileComponents();
  });

  it('shows the display name or email fallback as non-interactive menu context', () => {
    const fixture = TestBed.createComponent(SettingsComponent);
    user.set({ id: 'user-id', display_name: 'Ada', email: 'ada@example.test' });
    fixture.detectChanges();

    const accountName = fixture.nativeElement.querySelector('.settings-account-name');
    expect(accountName?.tagName).toBe('P');
    expect(accountName?.textContent?.trim()).toBe('Ada');
    expect(accountName?.querySelector('button, a, input, select')).toBeNull();

    user.set({ id: 'user-id', display_name: null, email: 'ada@example.test' });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.settings-account-name')?.textContent?.trim()).toBe(
      'ada@example.test',
    );
  });
});
