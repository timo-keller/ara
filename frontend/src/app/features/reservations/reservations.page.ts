import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Params, Router, RouterLink } from '@angular/router';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynDialogComponent } from '@synergy-design-system/angular/components/dialog';
import { SynInputComponent } from '@synergy-design-system/angular/components/input';
import { SynPaginationComponent } from '@synergy-design-system/angular/components/pagination';
import { SynSpinnerComponent } from '@synergy-design-system/angular/components/spinner';
import {
  Reservation,
  ReservationFilters,
  AssetCatalogueService,
} from '../assets/asset-catalogue.service';
import { localDateTimeToUtc } from '../assets/asset-detail.page';

type Action = 'return' | 'cancel';

export function reservationFiltersFromQuery(params: Params): ReservationFilters {
  const number = (name: string, fallback: number, min: number, max: number) => {
    const value = Number(params[name]);
    return Number.isInteger(value) && value >= min && value <= max ? value : fallback;
  };
  return {
    offset: number('offset', 0, 0, Number.MAX_SAFE_INTEGER),
    limit: number('limit', 10, 1, 100),
  };
}

export function reservationQueryParams(filters: ReservationFilters): Params {
  return {
    offset: filters.offset || null,
    limit: filters.limit === 10 ? null : filters.limit,
  };
}

/** Format UTC API instants in the browser's local timezone with an unambiguous 24-hour clock. */
export function localReservationTime(value: string): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.valueOf())) return 'Unavailable time';
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
    hourCycle: 'h23',
  }).format(timestamp);
}

export function allowedReservationActions(reservation: Reservation, now = new Date()): Action[] {
  if (reservation.status !== 'active') return [];
  const instant = now.getTime();
  if (new Date(reservation.starts_at).getTime() > instant) return ['cancel'];
  if (!reservation.ends_at || new Date(reservation.ends_at).getTime() > instant) return ['return'];
  return [];
}

@Component({
  imports: [
    RouterLink,
    SynAlertComponent,
    SynBadgeComponent,
    SynButtonComponent,
    SynDialogComponent,
    SynInputComponent,
    SynPaginationComponent,
    SynSpinnerComponent,
  ],
  selector: 'app-reservations-page',
  styleUrl: './reservations.page.scss',
  templateUrl: './reservations.page.html',
})
export class ReservationsPage {
  private readonly catalogue = inject(AssetCatalogueService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly reservations = signal<Reservation[]>([]);
  readonly total = signal(0);
  readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  readonly error = signal('');
  readonly success = signal('');
  readonly pendingAction = signal<{ action: Action; reservation: Reservation } | null>(null);
  readonly extensionFor = signal<Reservation | null>(null);
  readonly extensionEnd = signal('');
  readonly filters = signal<ReservationFilters>({ offset: 0, limit: 10 });
  readonly page = computed(() => Math.floor(this.filters().offset / this.filters().limit) + 1);
  readonly allowedActions = computed(
    () =>
      new Map(
        this.reservations().map((reservation) => [
          reservation.id,
          allowedReservationActions(reservation),
        ]),
      ),
  );

  constructor() {
    this.route.queryParams.subscribe((params) => {
      const filters = reservationFiltersFromQuery(params);
      this.filters.set(filters);
      this.load(filters);
    });
  }

  load(filters = this.filters()): void {
    this.state.set('loading');
    this.catalogue.mine(filters).subscribe({
      next: (result) => {
        this.reservations.set(result.items);
        this.total.set(result.total);
        this.state.set('ready');
      },
      error: () => this.state.set('error'),
    });
  }

  canExtend(reservation: Reservation): boolean {
    return reservation.status === 'active' && reservation.ends_at !== null;
  }

  reservationTime(reservation: Reservation): string {
    const start = localReservationTime(reservation.starts_at);
    return `${start} to ${reservation.ends_at ? localReservationTime(reservation.ends_at) : 'until returned'}`;
  }

  changePage(event: CustomEvent<{ currentPage: number }>): void {
    this.navigate({
      ...this.filters(),
      offset: (event.detail.currentPage - 1) * this.filters().limit,
    });
  }

  changePageSize(event: CustomEvent<{ currentPageSize: number }>): void {
    this.navigate({ ...this.filters(), limit: event.detail.currentPageSize, offset: 0 });
  }

  openExtension(reservation: Reservation): void {
    this.extensionFor.set(reservation);
    this.extensionEnd.set('');
    this.error.set('');
  }

  extend(): void {
    const reservation = this.extensionFor();
    const ends_at = localDateTimeToUtc(this.extensionEnd());
    if (!reservation || !ends_at) {
      this.error.set('Enter a valid local end time.');
      return;
    }
    this.catalogue.extendReservation(reservation.id, { ends_at }).subscribe({
      next: () => {
        this.extensionFor.set(null);
        this.success.set('Reservation extended and availability refreshed.');
        this.load();
      },
      error: (error: unknown) => this.handleMutationError(error),
    });
  }

  confirm(action: Action, reservation: Reservation): void {
    this.pendingAction.set({ action, reservation });
  }

  performConfirmedAction(): void {
    const pending = this.pendingAction();
    if (!pending) return;
    this.pendingAction.set(null);
    const request =
      pending.action === 'return'
        ? this.catalogue.returnReservation(pending.reservation.id)
        : this.catalogue.cancelReservation(pending.reservation.id);
    request.subscribe({
      next: () => {
        this.success.set(
          pending.action === 'return'
            ? 'Asset returned and availability refreshed.'
            : 'Reservation cancelled and availability refreshed.',
        );
        this.load();
      },
      error: (error: unknown) => this.handleMutationError(error),
    });
  }

  private handleMutationError(error: unknown): void {
    const body = (error as { error?: { error?: { code?: string; message?: string } } }).error
      ?.error;
    this.error.set(
      body?.code === 'reservation_conflict'
        ? 'That change conflicts with the current schedule. Review the asset schedule and choose an earlier end.'
        : body?.message || 'The reservation could not be changed. Refresh and try again.',
    );
    if (body?.code === 'reservation_conflict') this.load();
  }

  private navigate(filters: ReservationFilters): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: reservationQueryParams(filters),
    });
  }
}
