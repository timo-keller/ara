import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthService } from '../auth/auth.service';
import { NotificationService } from './notification.service';

const notification = (id: string, read_at: string | null = null) => ({
  id,
  reservation_id: null,
  kind: 'reservation_end_reminder:15',
  title: 'Reservation ending',
  body: 'Your reservation is scheduled to end.',
  scheduled_for: '2026-01-01T12:00:00Z',
  created_at: '2026-01-01T11:45:00Z',
  read_at,
});

describe('NotificationService', () => {
  let auth: AuthService;
  let http: HttpTestingController;
  let service: NotificationService;
  const originalNotification = Object.getOwnPropertyDescriptor(globalThis, 'Notification');

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    TestBed.resetTestingModule();
    vi.useRealTimers();
    if (originalNotification)
      Object.defineProperty(globalThis, 'Notification', originalNotification);
    else Reflect.deleteProperty(globalThis, 'Notification');
  });

  it('polls only while authenticated and stops after logout', async () => {
    service = TestBed.inject(NotificationService);
    await vi.advanceTimersByTimeAsync(0);
    http.expectNone('/api/notifications?limit=100');

    auth.state.set('authenticated');
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    const request = http.expectOne('/api/notifications?limit=100');
    request.flush({ items: [], total: 0, offset: 0, limit: 100 });

    auth.state.set('anonymous');
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(30_000);
    http.expectNone('/api/notifications?limit=100');
  });

  it('continues polling after a failed request and clears the error after a later success', async () => {
    service = TestBed.inject(NotificationService);
    auth.state.set('authenticated');
    TestBed.tick();
    await vi.advanceTimersByTimeAsync(0);
    http.expectOne('/api/notifications?limit=100').flush(null, {
      status: 500,
      statusText: 'Server Error',
    });
    expect(service.error()).toBe(true);

    await vi.advanceTimersByTimeAsync(30_000);
    http.expectOne('/api/notifications?limit=100').flush({
      items: [notification('one')],
      total: 1,
      offset: 0,
      limit: 100,
    });
    expect(service.error()).toBe(false);
    expect(service.unreadCount()).toBe(1);
  });

  it('tracks unread notifications and marks individual and all notifications read', () => {
    service = TestBed.inject(NotificationService);
    auth.state.set('authenticated');
    service.refresh();
    http.expectOne('/api/notifications?limit=100').flush({
      items: [notification('one'), notification('two', '2026-01-01T12:00:00Z')],
      total: 2,
      offset: 0,
      limit: 100,
    });
    expect(service.unreadCount()).toBe(1);

    service.markRead(service.notifications()[0]);
    http
      .expectOne('/api/notifications/one/read')
      .flush(notification('one', '2026-01-01T12:00:00Z'));
    expect(service.unreadCount()).toBe(0);

    service.notifications.set([notification('one'), notification('two')]);
    service.markAllRead();
    http
      .expectOne('/api/notifications/read')
      .flush(null, { status: 204, statusText: 'No Content' });
    expect(service.unreadCount()).toBe(0);
  });

  it('requests browser permission only from its explicit user action and handles denial', async () => {
    const requestPermission = vi.fn().mockResolvedValue('denied');
    Object.defineProperty(globalThis, 'Notification', {
      configurable: true,
      value: class {
        static permission = 'default';
        static requestPermission = requestPermission;
      },
    });
    service = TestBed.inject(NotificationService);

    expect(requestPermission).not.toHaveBeenCalled();
    service.requestBrowserPermission();
    await Promise.resolve();
    expect(requestPermission).toHaveBeenCalledOnce();
    expect(service.browserPermission()).toBe('denied');
  });

  it('keeps in-app notifications working when the browser API is unavailable', () => {
    Reflect.deleteProperty(globalThis, 'Notification');
    service = TestBed.inject(NotificationService);
    expect(service.browserPermission()).toBe('unavailable');
    service.notifications.set([notification('one')]);
    expect(service.unreadCount()).toBe(1);
    service.requestBrowserPermission();
  });

  it('raises each unread browser notification at most once per session', () => {
    const raised = vi.fn();
    Object.defineProperty(globalThis, 'Notification', {
      configurable: true,
      value: class {
        static permission = 'granted';
        constructor(...args: unknown[]) {
          raised(...args);
        }
      },
    });
    service = TestBed.inject(NotificationService);
    auth.state.set('authenticated');
    service.refresh();
    http.expectOne('/api/notifications?limit=100').flush({
      items: [notification('one')],
      total: 1,
      offset: 0,
      limit: 100,
    });
    service.refresh();
    http.expectOne('/api/notifications?limit=100').flush({
      items: [notification('one')],
      total: 1,
      offset: 0,
      limit: 100,
    });
    expect(raised).toHaveBeenCalledOnce();
  });
});
