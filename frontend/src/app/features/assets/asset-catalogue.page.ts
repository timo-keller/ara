import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynCardComponent } from '@synergy-design-system/angular/components/card';
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

@Component({
  imports: [
    RouterLink,
    SynAlertComponent,
    SynBadgeComponent,
    SynButtonComponent,
    SynCardComponent,
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

  constructor() {
    this.catalogue
      .groups()
      .subscribe({ next: ({ items }) => this.groups.set(items), error: () => undefined });
    this.load();
  }

  load(): void {
    this.state.set('loading');
    this.catalogue.list(this.filters()).subscribe({
      next: (page) => {
        this.items.set(page.items.filter((asset) => asset.archived_at === null));
        this.total.set(page.total);
        this.state.set('ready');
      },
      error: () => this.state.set('error'),
    });
  }

  changeFilter(name: 'groupId' | 'assetType' | 'availability' | 'text', value: string): void {
    this.filters.update((filters) => ({ ...filters, [name]: value, offset: 0 }));
    this.load();
  }

  changeSelectFilter(
    name: 'groupId' | 'assetType' | 'availability',
    value: string | number | (string | number)[],
  ): void {
    this.changeFilter(name, String(value));
  }

  changePage(event: CustomEvent<{ currentPage: number }>): void {
    this.filters.update((filters) => ({
      ...filters,
      offset: (event.detail.currentPage - 1) * filters.limit,
    }));
    this.load();
  }

  changePageSize(event: CustomEvent<{ currentPageSize: number }>): void {
    this.filters.update((filters) => ({
      ...filters,
      limit: event.detail.currentPageSize,
      offset: 0,
    }));
    this.load();
  }
}
