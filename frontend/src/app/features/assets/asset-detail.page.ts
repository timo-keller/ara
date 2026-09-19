import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynCardComponent } from '@synergy-design-system/angular/components/card';
import { SynDialogComponent } from '@synergy-design-system/angular/components/dialog';
import { SynInputComponent } from '@synergy-design-system/angular/components/input';
import { SynSpinnerComponent } from '@synergy-design-system/angular/components/spinner';
import {
  Asset,
  AssetCatalogueService,
  Reservation,
  ReservationCreate,
} from './asset-catalogue.service';

export function localDateTimeToUtc(value: string): string | null {
  const date = new Date(value);
  return value && !Number.isNaN(date.getTime()) ? date.toISOString() : null;
}

export function reservationPayload(
  assetId: string,
  startsAt: string,
  endsAt: string,
): ReservationCreate | null {
  const starts_at = localDateTimeToUtc(startsAt);
  const ends_at = endsAt ? localDateTimeToUtc(endsAt) : null;
  if (!starts_at || (endsAt && !ends_at)) return null;
  return ends_at ? { asset_id: assetId, starts_at, ends_at } : { asset_id: assetId, starts_at };
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
  selector: 'app-asset-detail-page',
  styleUrl: './asset-detail.page.scss',
  templateUrl: './asset-detail.page.html',
})
export class AssetDetailPage {
  private readonly catalogue = inject(AssetCatalogueService);
  private readonly route = inject(ActivatedRoute);
  readonly asset = signal<Asset | null>(null);
  readonly reservations = signal<Reservation[]>([]);
  readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  readonly startsAt = signal('');
  readonly endsAt = signal('');
  readonly openEndedConfirmationOpen = signal(false);
  readonly reservationError = signal('');
  readonly reservationSuccess = signal('');
  readonly reserving = signal(false);

  constructor() {
    this.load();
  }

  load(): void {
    const id = this.route.snapshot.paramMap.get('assetId');
    if (!id) {
      this.state.set('error');
      return;
    }
    this.state.set('loading');
    this.catalogue.get(id).subscribe({
      next: (asset) => {
        if (asset.archived_at) {
          this.state.set('error');
          return;
        }
        this.asset.set(asset);
        this.catalogue.schedule(id).subscribe({
          next: ({ items }) => {
            this.reservations.set(items);
            this.state.set('ready');
          },
          error: () => this.state.set('error'),
        });
      },
      error: () => this.state.set('error'),
    });
  }

  selectNow(): void {
    const now = new Date();
    now.setSeconds(0, 0);
    this.startsAt.set(this.localInputValue(now));
  }

  submitReservation(): void {
    const current = this.asset();
    const payload = current && reservationPayload(current.id, this.startsAt(), this.endsAt());
    if (!payload) {
      this.reservationError.set('Enter a valid local start time and, when used, end time.');
      return;
    }
    if (!payload.ends_at) {
      this.openEndedConfirmationOpen.set(true);
      return;
    }
    this.createReservation(payload);
  }

  confirmOpenEndedReservation(): void {
    const current = this.asset();
    const payload = current && reservationPayload(current.id, this.startsAt(), this.endsAt());
    this.openEndedConfirmationOpen.set(false);
    if (payload && !payload.ends_at) this.createReservation(payload);
  }

  cancelOpenEndedConfirmation(): void {
    this.openEndedConfirmationOpen.set(false);
  }

  private createReservation(payload: ReservationCreate): void {
    this.reservationError.set('');
    this.reservationSuccess.set('');
    this.reserving.set(true);
    this.catalogue.createReservation(payload).subscribe({
      next: () => {
        this.reserving.set(false);
        this.reservationSuccess.set('Reservation created. The schedule below has been refreshed.');
        this.load();
      },
      error: (error: unknown) => {
        this.reserving.set(false);
        this.reservationError.set(this.reservationErrorMessage(error));
        if (this.reservationError().includes('already reserved')) this.load();
      },
    });
  }

  private localInputValue(date: Date): string {
    const offsetDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
    return offsetDate.toISOString().slice(0, 16);
  }

  private reservationErrorMessage(error: unknown): string {
    const body = (error as { error?: { error?: { code?: string; message?: string } } }).error
      ?.error;
    if (body?.code === 'reservation_conflict') {
      return 'This time conflicts with the current schedule. Choose a gap shown below, then try again.';
    }
    return (
      body?.message || 'The reservation could not be created. Check the schedule and try again.'
    );
  }

  safeRemoteUrl(value: string | null): string | null {
    if (!value) return null;
    try {
      const url = new URL(value);
      return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null;
    } catch {
      return null;
    }
  }
}
