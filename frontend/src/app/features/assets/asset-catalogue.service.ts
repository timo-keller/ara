import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

export type Availability = '' | 'available' | 'reserved';

export interface AssetFilters {
  groupId: string;
  assetType: string;
  availability: Availability;
  text: string;
  offset: number;
  limit: number;
}

export interface Asset {
  id: string;
  group_id: string;
  asset_type: string;
  name: string;
  description: string | null;
  operational_metadata: Record<string, unknown> | null;
  remote_host: string | null;
  remote_url: string | null;
  operating_system: string | null;
  access_instructions: string | null;
  webex_room_id: string | null;
  archived_at: string | null;
}

export interface CatalogueAsset extends Asset {
  availability: 'available' | 'reserved';
}

export interface AssetPage {
  items: CatalogueAsset[];
  total: number;
  offset: number;
  limit: number;
}

export interface Group {
  id: string;
  name: string;
}

export interface Reservation {
  id: string;
  asset_id: string;
  asset_name: string | null;
  starts_at: string;
  ends_at: string | null;
  status: 'active' | 'returned' | 'cancelled' | 'ended';
}

export interface ReservationCreate {
  asset_id: string;
  starts_at: string;
  ends_at?: string;
}

export interface ReservationExtension {
  ends_at: string;
}

export function assetQuery(filters: AssetFilters): HttpParams {
  let params = new HttpParams().set('offset', filters.offset).set('limit', filters.limit);
  if (filters.groupId) params = params.set('group_id', filters.groupId);
  if (filters.assetType) params = params.set('asset_type', filters.assetType);
  if (filters.availability) params = params.set('availability', filters.availability);
  if (filters.text.trim()) params = params.set('text', filters.text.trim());
  // The public catalogue is explicitly active-only, even if a server default changes.
  return params.set('archived', false);
}

@Injectable({ providedIn: 'root' })
export class AssetCatalogueService {
  private readonly http = inject(HttpClient);

  list(filters: AssetFilters) {
    return this.http.get<AssetPage>('/api/assets', { params: assetQuery(filters) });
  }

  get(assetId: string) {
    return this.http.get<Asset>(`/api/assets/${assetId}`);
  }

  groups() {
    return this.http.get<{ items: Group[] }>('/api/groups', {
      params: new HttpParams().set('archived', false).set('limit', 100),
    });
  }

  schedule(assetId: string) {
    return this.http.get<{ items: Reservation[] }>(`/api/assets/${assetId}/reservations`, {
      params: new HttpParams().set('limit', 10),
    });
  }

  mine() {
    return this.http.get<{ items: Reservation[] }>('/api/reservations/mine');
  }

  createReservation(payload: ReservationCreate) {
    return this.http.post<Reservation>('/api/reservations', payload);
  }

  extendReservation(reservationId: string, payload: ReservationExtension) {
    return this.http.post<Reservation>(`/api/reservations/${reservationId}/extend`, payload);
  }

  returnReservation(reservationId: string) {
    return this.http.post<Reservation>(`/api/reservations/${reservationId}/return`, {});
  }

  cancelReservation(reservationId: string) {
    return this.http.post<Reservation>(`/api/reservations/${reservationId}/cancel`, {});
  }
}
