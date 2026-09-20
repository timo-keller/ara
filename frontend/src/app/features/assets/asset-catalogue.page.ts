import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Params, Router, RouterLink } from '@angular/router';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynCardComponent } from '@synergy-design-system/angular/components/card';
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
} from './asset-catalogue.service';

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
    SynBadgeComponent,
    SynButtonComponent,
    SynCardComponent,
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
  readonly groups = signal<Group[]>([]);
  readonly items = signal<CatalogueAsset[]>([]);
  readonly total = signal(0);
  readonly state = signal<'loading' | 'ready' | 'error'>('loading');
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
    this.state.set('loading');
    this.catalogue.list(filters).subscribe({
      next: (page) => {
        this.items.set(page.items.filter((asset) => asset.archived_at === null));
        this.total.set(page.total);
        this.state.set('ready');
      },
      error: () => this.state.set('error'),
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
