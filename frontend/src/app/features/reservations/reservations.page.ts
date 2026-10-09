import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Params, Router, RouterLink } from '@angular/router';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynComboboxComponent } from '@synergy-design-system/angular/components/combobox';
import { SynDialogComponent } from '@synergy-design-system/angular/components/dialog';
import { SynInputComponent } from '@synergy-design-system/angular/components/input';
import { SynOptionComponent } from '@synergy-design-system/angular/components/option';
import { SynPaginationComponent } from '@synergy-design-system/angular/components/pagination';
import { SynSpinnerComponent } from '@synergy-design-system/angular/components/spinner';
import { ToastService } from '../../core/notifications/toast.service';
import {
  Reservation,
  ReservationFilters,
  ReservationLifecycle,
  AssetCatalogueService,
} from '../assets/asset-catalogue.service';
import { localDateTimeToUtc } from '../assets/asset-detail.page';

type Action = 'return' | 'cancel';
const lifecycles: ReservationLifecycle[] = [
  'current',
  'future',
  'expired',
  'returned',
  'cancelled',
  'ended',
];

function normalizeLifecycles(values: unknown[]): ReservationLifecycle[] {
  const selected = new Set(
    values.filter(
      (value): value is ReservationLifecycle =>
        typeof value === 'string' && lifecycles.includes(value as ReservationLifecycle),
    ),
  );
  return lifecycles.filter((lifecycle) => selected.has(lifecycle));
}

function lifecycleOptionLabel(lifecycle: ReservationLifecycle): string {
  return lifecycle.charAt(0).toUpperCase() + lifecycle.slice(1);
}

const defaults: ReservationFilters = {
  offset: 0,
  limit: 10,
  asset_name: '',
  asset_type: '',
  timespan_from: '',
  timespan_to: '',
  lifecycle: [],
};

function validUtc(value: unknown): string {
  if (
    typeof value !== 'string' ||
    !/Z$|\+00:00$/.test(value) ||
    Number.isNaN(new Date(value).valueOf())
  )
    return '';
  return new Date(value).toISOString();
}

export function reservationFiltersFromQuery(params: Params): ReservationFilters {
  const number = (name: string, fallback: number, min: number, max: number) => {
    const value = Number(params[name]);
    return Number.isInteger(value) && value >= min && value <= max ? value : fallback;
  };
  return {
    ...defaults,
    offset: number('offset', defaults.offset, 0, Number.MAX_SAFE_INTEGER),
    limit: number('limit', defaults.limit, 1, 100),
    asset_name: typeof params['asset_name'] === 'string' ? params['asset_name'] : '',
    asset_type: typeof params['asset_type'] === 'string' ? params['asset_type'] : '',
    timespan_from: validUtc(params['timespan_from']),
    timespan_to: validUtc(params['timespan_to']),
    lifecycle: normalizeLifecycles(
      Array.isArray(params['lifecycle']) ? params['lifecycle'] : [params['lifecycle']],
    ),
  };
}

export function reservationQueryParams(filters: ReservationFilters): Params {
  const lifecycle = normalizeLifecycles(filters.lifecycle);
  return {
    offset: filters.offset || null,
    limit: filters.limit === 10 ? null : filters.limit,
    asset_name: filters.asset_name.trim() || null,
    asset_type: filters.asset_type.trim() || null,
    timespan_from: filters.timespan_from || null,
    timespan_to: filters.timespan_to || null,
    lifecycle: lifecycle.length ? lifecycle : null,
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

export function allowedReservationActions(reservation: Reservation): Action[] {
  if (reservation.status !== 'active') return [];
  if (reservation.lifecycle === 'future') return ['cancel'];
  if (reservation.lifecycle === 'current' || reservation.lifecycle === 'expired') return ['return'];
  return [];
}

export function lifecycleLabel(reservation: Reservation): string {
  const lifecycle = reservation.lifecycle || reservation.status;
  return lifecycle.charAt(0).toUpperCase() + lifecycle.slice(1);
}

export function utcToLocalDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return '';
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.valueOf() - offset).toISOString().slice(0, 16);
}

@Component({
  imports: [
    RouterLink,
    SynAlertComponent,
    SynBadgeComponent,
    SynButtonComponent,
    SynComboboxComponent,
    SynDialogComponent,
    SynInputComponent,
    SynOptionComponent,
    SynPaginationComponent,
    SynSpinnerComponent,
  ],
  selector: 'app-reservations-page',
  styleUrl: './reservations.page.scss',
  templateUrl: './reservations.page.html',
})
export class ReservationsPage {
  private readonly catalogue = inject(AssetCatalogueService);
  private readonly toast = inject(ToastService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly reservations = signal<Reservation[]>([]);
  readonly total = signal(0);
  readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  readonly pendingAction = signal<{ action: Action; reservation: Reservation } | null>(null);
  readonly extensionFor = signal<Reservation | null>(null);
  readonly extensionEnd = signal('');
  readonly filters = signal<ReservationFilters>(defaults);
  readonly lifecycleOptions = lifecycles;
  readonly lifecycleOptionLabel = lifecycleOptionLabel;
  readonly lifecycleLabel = lifecycleLabel;
  readonly utcToLocalDateTime = utcToLocalDateTime;
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

  updateTextFilter(name: 'asset_name' | 'asset_type', value: string): void {
    this.navigate({ ...this.filters(), [name]: value, offset: 0 });
  }

  updateTimeFilter(name: 'timespan_from' | 'timespan_to', localValue: string): void {
    this.navigate({ ...this.filters(), [name]: localDateTimeToUtc(localValue) || '', offset: 0 });
  }

  updateLifecycles(value: string | number | (string | number)[]): void {
    if (!Array.isArray(value)) return;
    this.navigate({ ...this.filters(), lifecycle: normalizeLifecycles(value), offset: 0 });
  }

  hasFilters(): boolean {
    const filters = this.filters();
    return !!(
      filters.asset_name ||
      filters.asset_type ||
      filters.timespan_from ||
      filters.timespan_to ||
      filters.lifecycle.length
    );
  }

  clearFilters(): void {
    this.navigate({ ...defaults, limit: this.filters().limit });
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
  }

  extend(): void {
    const reservation = this.extensionFor();
    const ends_at = localDateTimeToUtc(this.extensionEnd());
    if (!reservation || !ends_at) {
      this.toast.error('Enter a valid local end time.');
      return;
    }
    this.catalogue.extendReservation(reservation.id, { ends_at }).subscribe({
      next: () => {
        this.extensionFor.set(null);
        this.toast.success('Reservation extended and availability refreshed.');
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
        this.toast.success(
          pending.action === 'return'
            ? 'Asset returned and availability refreshed.'
            : 'Reservation cancelled and availability refreshed.',
        );
        this.load();
      },
      error: (error: unknown) => this.handleMutationError(error, pending.action === 'return'),
    });
  }

  private handleMutationError(error: unknown, reload = false): void {
    const body = (error as { error?: { error?: { code?: string; message?: string } } }).error
      ?.error;
    this.toast.error(
      body?.code === 'reservation_conflict'
        ? 'That change conflicts with the current schedule. Review the asset schedule and choose an earlier end.'
        : body?.message || 'The reservation could not be changed. Refresh and try again.',
    );
    if (body?.code === 'reservation_conflict' || reload) this.load();
  }

  private navigate(filters: ReservationFilters): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: reservationQueryParams(filters),
    });
  }
}
