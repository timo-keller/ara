import { HttpClient } from '@angular/common/http';
import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { Subscription, catchError, of, switchMap, timer } from 'rxjs';
import { AuthService } from '../auth/auth.service';

export interface AppNotification {
  id: string;
  reservation_id: string | null;
  kind: string;
  title: string;
  body: string | null;
  scheduled_for: string | null;
  created_at: string;
  read_at: string | null;
}

interface NotificationPage {
  items: AppNotification[];
  total: number;
  offset: number;
  limit: number;
}

type BrowserNotificationConstructor = typeof Notification;

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private polling?: Subscription;
  private readonly raisedIds = new Set<string>();

  readonly notifications = signal<AppNotification[]>([]);
  readonly loading = signal(false);
  readonly error = signal(false);
  readonly unreadCount = computed(
    () => this.notifications().filter((notification) => notification.read_at === null).length,
  );
  readonly browserNotificationsAvailable = typeof Notification !== 'undefined';
  readonly browserPermission = signal<NotificationPermission | 'unavailable'>(
    this.browserNotificationsAvailable ? Notification.permission : 'unavailable',
  );

  constructor() {
    effect(() => {
      if (this.auth.state() === 'authenticated') this.startPolling();
      else this.stopPolling();
    });
  }

  refresh(): void {
    if (this.auth.state() !== 'authenticated') return;
    this.loading.set(true);
    this.http.get<NotificationPage>('/api/notifications', { params: { limit: 100 } }).subscribe({
      next: ({ items }) => {
        this.notifications.set(items);
        this.error.set(false);
        this.loading.set(false);
        this.raiseUnreadBrowserNotifications(items);
      },
      error: () => {
        this.error.set(true);
        this.loading.set(false);
      },
    });
  }

  markRead(notification: AppNotification): void {
    if (notification.read_at !== null) return;
    this.http.post<AppNotification>(`/api/notifications/${notification.id}/read`, {}).subscribe({
      next: (updated) => this.replace(updated),
      error: () => this.error.set(true),
    });
  }

  markAllRead(): void {
    if (this.unreadCount() === 0) return;
    this.http.post<void>('/api/notifications/read', {}).subscribe({
      next: () => {
        const readAt = new Date().toISOString();
        this.notifications.update((items) =>
          items.map((notification) => ({
            ...notification,
            read_at: notification.read_at ?? readAt,
          })),
        );
      },
      error: () => this.error.set(true),
    });
  }

  requestBrowserPermission(): void {
    const BrowserNotification = this.browserNotification();
    if (!BrowserNotification || this.browserPermission() !== 'default') return;
    void BrowserNotification.requestPermission().then((permission) => {
      this.browserPermission.set(permission);
      this.raiseUnreadBrowserNotifications(this.notifications());
    });
  }

  private startPolling(): void {
    if (this.polling) return;
    this.polling = timer(0, 30_000)
      .pipe(
        switchMap(() =>
          this.http
            .get<NotificationPage>('/api/notifications', { params: { limit: 100 } })
            .pipe(catchError(() => of(null))),
        ),
      )
      .subscribe((page) => {
        if (!page) {
          this.error.set(true);
          return;
        }
        this.notifications.set(page.items);
        this.error.set(false);
        this.raiseUnreadBrowserNotifications(page.items);
      });
  }

  private stopPolling(): void {
    this.polling?.unsubscribe();
    this.polling = undefined;
    this.notifications.set([]);
  }

  private replace(updated: AppNotification): void {
    this.notifications.update((items) =>
      items.map((notification) => (notification.id === updated.id ? updated : notification)),
    );
  }

  private browserNotification(): BrowserNotificationConstructor | undefined {
    return typeof Notification === 'undefined' ? undefined : Notification;
  }

  private raiseUnreadBrowserNotifications(notifications: AppNotification[]): void {
    const BrowserNotification = this.browserNotification();
    if (!BrowserNotification || this.browserPermission() !== 'granted') return;
    for (const notification of notifications) {
      if (notification.read_at !== null || this.raisedIds.has(notification.id)) continue;
      this.raisedIds.add(notification.id);
      new BrowserNotification(notification.title, { body: notification.body ?? undefined });
    }
  }
}
