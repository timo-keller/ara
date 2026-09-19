import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Asset, Group } from './asset-catalogue.service';

export interface AssetDraftPayload {
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
}

@Injectable({ providedIn: 'root' })
export class AssetAdministrationService {
  private readonly http = inject(HttpClient);

  groups() {
    return this.http.get<{ items: Group[] }>('/api/groups', {
      params: new HttpParams().set('archived', false).set('limit', 100),
    });
  }

  list(archived: boolean) {
    return this.http.get<{ items: Asset[] }>('/api/assets', {
      params: new HttpParams().set('archived', archived).set('limit', 100),
    });
  }

  create(payload: AssetDraftPayload) {
    return this.http.post<Asset>('/api/assets', payload);
  }

  update(assetId: string, payload: Omit<AssetDraftPayload, 'group_id'>) {
    return this.http.patch<Asset>(`/api/assets/${assetId}`, payload);
  }

  archive(assetId: string) {
    return this.http.post<Asset>(`/api/assets/${assetId}/archive`, {});
  }

  reactivate(assetId: string) {
    return this.http.post<Asset>(`/api/assets/${assetId}/reactivate`, {});
  }
}
