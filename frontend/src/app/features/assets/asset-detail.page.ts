import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynCardComponent } from '@synergy-design-system/angular/components/card';
import { SynSpinnerComponent } from '@synergy-design-system/angular/components/spinner';
import { Asset, AssetCatalogueService, Reservation } from './asset-catalogue.service';

@Component({
  imports: [
    DatePipe,
    RouterLink,
    SynAlertComponent,
    SynBadgeComponent,
    SynButtonComponent,
    SynCardComponent,
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
