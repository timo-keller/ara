import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { App } from './app';
import { routes } from './app.routes';
import { NotificationService } from './core/notifications/notification.service';

class ResizeObserverStub {
  disconnect(): undefined {
    return undefined;
  }
  observe(): undefined {
    return undefined;
  }
  unobserve(): undefined {
    return undefined;
  }
}

interface HeaderElement extends HTMLElement {
  connectSideNavigation(sideNav: HTMLElement): void;
}

describe('App', () => {
  beforeEach(async () => {
    globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter(routes)],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('omits effective roles diagnostics while retaining owner navigation', () => {
    const headerElement = customElements.get('syn-header') as unknown as {
      prototype: HeaderElement;
    };
    const connectSideNavigation = vi.spyOn(headerElement.prototype, 'connectSideNavigation');
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/auth/session').flush({
      authenticated: true,
      user: { id: 'user-id', display_name: 'Ada', email: 'ada@example.test' },
      roles: { is_owner: true, group_roles: {} },
    });
    fixture.detectChanges();

    const rail = fixture.nativeElement.querySelector('syn-side-nav');
    expect(rail?.getAttribute('variant')).toBe('rail');
    expect(connectSideNavigation).toHaveBeenCalledWith(rail);
    const accountNavigation = fixture.nativeElement.querySelector(
      'nav[aria-label="Account"]',
    ) as HTMLElement;
    expect(Array.from(accountNavigation.children).map((child) => child.tagName)).toEqual([
      'APP-SETTINGS',
    ]);
    expect(accountNavigation.querySelector('.account-name')).toBeNull();
    expect(fixture.nativeElement.querySelector('.settings-account-name')?.textContent?.trim()).toBe(
      'Ada',
    );
    expect(fixture.nativeElement.textContent).not.toContain('Effective roles');
    expect(fixture.nativeElement.querySelector('.effective-roles')).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('Home');
    const reservationsNavigation = fixture.nativeElement.querySelector(
      'syn-nav-item[href="/reservations"]',
    ) as HTMLElement;
    expect(reservationsNavigation?.textContent?.trim()).toBe('My reservations');
    fixture.componentInstance.currentUrl.set('/reservations');
    fixture.detectChanges();
    expect(reservationsNavigation?.getAttribute('current')).toBe('');
    expect(fixture.nativeElement.textContent).toContain('Administration');
    expect(fixture.nativeElement.textContent).toContain('Audit history');
    const navigationIconName = (label: string) => {
      const navigationItems = fixture.nativeElement.querySelectorAll(
        'syn-nav-item',
      ) as NodeListOf<HTMLElement>;
      const item = Array.from(navigationItems).find(
        (element) => element.textContent?.trim() === label,
      );
      return item?.querySelector('syn-icon')?.getAttribute('name');
    };
    const assetsIcon = navigationIconName('Assets');
    const manageAssetsIcon = navigationIconName('Manage assets');
    const auditHistoryIcon = navigationIconName('Audit history');
    const administrationIcon = navigationIconName('Administration');
    expect(assetsIcon).toBe('inventory');
    expect(manageAssetsIcon).toBe('admin_panel_settings');
    expect(assetsIcon).not.toBe(manageAssetsIcon);
    expect(auditHistoryIcon).toBe('history');
    expect(administrationIcon).toBe('settings');
    expect(auditHistoryIcon).not.toBe(administrationIcon);
    TestBed.inject(NotificationService).notifications.set([
      {
        id: 'one',
        reservation_id: null,
        kind: 'reservation_end_reminder:15',
        title: 'Reservation ending',
        body: null,
        scheduled_for: null,
        created_at: '2026-01-01T00:00:00Z',
        read_at: null,
      },
      {
        id: 'two',
        reservation_id: null,
        kind: 'reservation_end_reminder:15',
        title: 'Another reservation ending',
        body: null,
        scheduled_for: null,
        created_at: '2026-01-01T00:00:00Z',
        read_at: null,
      },
    ]);
    fixture.detectChanges();
    expect(
      fixture.nativeElement.querySelector('app-settings syn-button')?.getAttribute('aria-label'),
    ).toBe('Settings, 2 unread notifications');
    expect(
      fixture.nativeElement.querySelector('app-settings syn-button')?.getAttribute('title'),
    ).toBe('Settings');
    expect(fixture.nativeElement.querySelector('app-settings syn-badge')?.textContent?.trim()).toBe(
      '2',
    );
    expect(fixture.nativeElement.querySelector('app-settings app-notifications')).toBeTruthy();
    http.verify();
  });
});
