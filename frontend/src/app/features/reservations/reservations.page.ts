import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynCardComponent } from '@synergy-design-system/angular/components/card';
import { SynDialogComponent } from '@synergy-design-system/angular/components/dialog';
import { SynInputComponent } from '@synergy-design-system/angular/components/input';
import { SynSpinnerComponent } from '@synergy-design-system/angular/components/spinner';
import { Reservation, AssetCatalogueService } from '../assets/asset-catalogue.service';
import { localDateTimeToUtc } from '../assets/asset-detail.page';

type Action = 'return' | 'cancel';

export function allowedReservationActions(reservation: Reservation, now = new Date()): Action[] {
  if (reservation.status !== 'active') return [];
  const instant = now.getTime();
  if (new Date(reservation.starts_at).getTime() > instant) return ['cancel'];
  if (!reservation.ends_at || new Date(reservation.ends_at).getTime() > instant) return ['return'];
  return [];
}

@Component({
  imports: [
    DatePipe,
    RouterLink,
    SynAlertComponent,
    SynBadgeComponent,
    SynButtonComponent,
    SynCardComponent,
    SynDialogComponent,
    SynInputComponent,
    SynSpinnerComponent,
  ],
  selector: 'app-reservations-page',
  styleUrl: './reservations.page.scss',
  templateUrl: './reservations.page.html',
})
export class ReservationsPage {
  private readonly catalogue = inject(AssetCatalogueService);
  readonly reservations = signal<Reservation[]>([]);
  readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  readonly error = signal('');
  readonly success = signal('');
  readonly pendingAction = signal<{ action: Action; reservation: Reservation } | null>(null);
  readonly extensionFor = signal<Reservation | null>(null);
  readonly extensionEnd = signal('');
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
    this.load();
  }

  load(): void {
    this.state.set('loading');
    this.catalogue.mine().subscribe({
      next: ({ items }) => {
        this.reservations.set(items);
        this.state.set('ready');
      },
      error: () => this.state.set('error'),
    });
  }

  canExtend(reservation: Reservation): boolean {
    return reservation.status === 'active' && reservation.ends_at !== null;
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
}
