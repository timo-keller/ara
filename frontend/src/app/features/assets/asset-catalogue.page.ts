import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Params, Router, RouterLink } from '@angular/router';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynComboboxComponent } from '@synergy-design-system/angular/components/combobox';
import { SynInputComponent } from '@synergy-design-system/angular/components/input';
import { SynOptionComponent } from '@synergy-design-system/angular/components/option';
import { SynPaginationComponent } from '@synergy-design-system/angular/components/pagination';
import { SynSelectComponent } from '@synergy-design-system/angular/components/select';
import { SynSpinnerComponent } from '@synergy-design-system/angular/components/spinner';
import {
  AssetCatalogueService,
  AssetFilters,
  CatalogueAsset,
  Group,
  Reservation,
} from './asset-catalogue.service';
import { QUICK_BOOKING_DURATIONS, availableBookingDurations } from './quick-booking';

export function assetFiltersFromQuery(params: Params): AssetFilters {
  const number = (name: string, fallback: number, min: number, max: number) => {
    const value = Number(params[name]);
    return Number.isInteger(value) && value >= min && value <= max ? value : fallback;
  };
  return {
    groupId: String(params['group_id'] ?? ''),
    // Keep the legacy REST query name so existing catalogue links continue to work.
    assetType: String(params['asset_type'] ?? ''),
    availability: ['available', 'reserved'].includes(String(params['availability']))
      ? (String(params['availability']) as AssetFilters['availability'])
      : '',
    text: String(params['text'] ?? ''),
    offset: number('offset', 0, 0, Number.MAX_SAFE_INTEGER),
    limit: number('limit', 10, 1, 100),
  };
}

export function assetQueryParams(filters: AssetFilters): Params {
  return {
    group_id: filters.groupId || null,
    asset_type: filters.assetType || null,
    availability: filters.availability || null,
    text: filters.text || null,
    offset: filters.offset || null,
    limit: filters.limit === 10 ? null : filters.limit,
  };
}

@Component({
  imports: [
    RouterLink,
    SynAlertComponent,
    SynButtonComponent,
    SynComboboxComponent,
    SynInputComponent,
    SynOptionComponent,
    SynPaginationComponent,
    SynSelectComponent,
    SynSpinnerComponent,
  ],
  selector: 'app-asset-catalogue-page',
  styleUrl: './asset-catalogue.page.scss',
  templateUrl: './asset-catalogue.page.html',
})
export class AssetCataloguePage {
  private readonly catalogue = inject(AssetCatalogueService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private loadVersion = 0;
  readonly groups = signal<Group[]>([]);
  readonly items = signal<CatalogueAsset[]>([]);
  readonly total = signal(0);
  readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  readonly bookingAssetId = signal<string | null>(null);
  readonly bookingError = signal('');
  readonly bookingSuccess = signal('');
  readonly schedules = signal<Record<string, Reservation[]>>({});
  readonly bookingDurations = QUICK_BOOKING_DURATIONS;
  readonly filters = signal<AssetFilters>({
    groupId: '',
    assetType: '',
    availability: '',
    text: '',
    offset: 0,
    limit: 10,
  });
  readonly page = computed(() => Math.floor(this.filters().offset / this.filters().limit) + 1);
  /** Types returned by the authorized active catalogue endpoint, with no client-side vocabulary. */
  readonly assetTypes = computed(() =>
    [...new Set(this.items().map((asset) => asset.asset_type))].sort((first, second) =>
      first.localeCompare(second),
    ),
  );

  constructor() {
    this.catalogue
      .groups()
      .subscribe({ next: ({ items }) => this.groups.set(items), error: () => undefined });
    this.route.queryParams.subscribe((params) => {
      const filters = assetFiltersFromQuery(params);
      this.filters.set(filters);
      this.load(filters);
    });
  }

  load(filters = this.filters()): void {
    const version = ++this.loadVersion;
    this.state.set('loading');
    this.schedules.set({});
    this.catalogue.list(filters).subscribe({
      next: (page) => {
        if (version !== this.loadVersion) return;
        this.items.set(page.items.filter((asset) => asset.archived_at === null));
        this.total.set(page.total);
        this.state.set('ready');
        for (const asset of this.items()) {
          if (asset.availability !== 'available') continue;
          this.catalogue.schedule(asset.id).subscribe({
            next: ({ items }) => {
              if (version === this.loadVersion) {
                this.schedules.update((schedules) => ({ ...schedules, [asset.id]: items }));
              }
            },
            error: () => undefined,
          });
        }
      },
      error: () => this.state.set('error'),
    });
  }

  canBookNow(asset: CatalogueAsset, hours: number): boolean {
    const schedule = this.schedules()[asset.id];
    return (
      !!schedule && availableBookingDurations(schedule).some((duration) => duration.hours === hours)
    );
  }

  book(asset: CatalogueAsset, hours: number): void {
    if (asset.availability !== 'available' || this.bookingAssetId()) return;
    if (!this.canBookNow(asset, hours)) return;
    const start = new Date();
    this.bookingError.set('');
    this.bookingSuccess.set('');
    this.bookingAssetId.set(asset.id);
    this.catalogue
      .createReservation({
        asset_id: asset.id,
        starts_at: start.toISOString(),
        ends_at: new Date(start.getTime() + hours * 3_600_000).toISOString(),
      })
      .subscribe({
        next: () => {
          this.bookingAssetId.set(null);
          const duration = QUICK_BOOKING_DURATIONS.find((option) => option.hours === hours)?.label;
          this.bookingSuccess.set(`${asset.name} booked for ${duration}.`);
          this.load();
        },
        error: (error: unknown) => {
          this.bookingAssetId.set(null);
          const body = (error as { error?: { error?: { code?: string; message?: string } } }).error
            ?.error;
          this.bookingError.set(
            body?.code === 'reservation_conflict'
              ? `Could not book ${asset.name}: another reservation overlaps this period. Try a shorter duration or view the asset's schedule.`
              : body?.message || `Could not book ${asset.name}. Please try again.`,
          );
          if (body?.code === 'reservation_conflict') this.load();
        },
      });
  }

  changeFilter(name: 'groupId' | 'assetType' | 'availability' | 'text', value: string): void {
    const filters = { ...this.filters(), [name]: value, offset: 0 } as AssetFilters;
    this.navigate(filters);
  }

  changeSelectFilter(
    name: 'groupId' | 'assetType' | 'availability',
    value: string | number | (string | number)[],
  ): void {
    this.changeFilter(name, String(value));
  }

  changeAssetType(value: string | number | (string | number)[]): void {
    const type = Array.isArray(value) ? String(value[0] ?? '') : String(value);
    if (!type || this.assetTypes().includes(type)) this.changeFilter('assetType', type);
  }

  changePage(event: CustomEvent<{ currentPage: number }>): void {
    const filters = {
      ...this.filters(),
      offset: (event.detail.currentPage - 1) * this.filters().limit,
    };
    this.navigate(filters);
  }

  changePageSize(event: CustomEvent<{ currentPageSize: number }>): void {
    const filters = { ...this.filters(), limit: event.detail.currentPageSize, offset: 0 };
    this.navigate(filters);
  }

  private navigate(filters: AssetFilters): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: assetQueryParams(filters),
    });
  }
}
