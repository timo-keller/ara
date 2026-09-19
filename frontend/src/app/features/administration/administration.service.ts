import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

export interface Group {
  id: string;
  name: string;
  description: string | null;
  archived_at: string | null;
}

export interface RoleMapping {
  id: string;
  group_id: string;
  expression: string;
  role: 'user' | 'group_admin';
  enabled: boolean;
  priority: number;
  archived_at: string | null;
}

export interface ApiErrorDetail {
  location?: string[];
  message?: string;
  reservation_id?: string;
  asset_id?: string;
  resolution?: string;
}

export interface ApiError {
  error?: { code: string; message: string; details?: ApiErrorDetail[] };
}

@Injectable({ providedIn: 'root' })
export class AdministrationService {
  private readonly http = inject(HttpClient);

  groups(archived?: boolean) {
    let params = new HttpParams().set('limit', 100);
    if (archived !== undefined) params = params.set('archived', archived);
    return this.http.get<{ items: Group[] }>('/api/groups', { params });
  }

  createGroup(payload: Pick<Group, 'name' | 'description'>) {
    return this.http.post<Group>('/api/groups', payload);
  }

  updateGroup(id: string, payload: Partial<Pick<Group, 'name' | 'description'>>) {
    return this.http.patch<Group>(`/api/groups/${id}`, payload);
  }

  archiveGroup(id: string) {
    return this.http.post<Group>(`/api/groups/${id}/archive`, {});
  }

  reactivateGroup(id: string) {
    return this.http.post<Group>(`/api/groups/${id}/reactivate`, {});
  }

  mappings() {
    return this.http.get<{ items: RoleMapping[] }>('/api/role-mappings', {
      params: new HttpParams().set('archived', false).set('limit', 100),
    });
  }

  createMapping(payload: Omit<RoleMapping, 'id' | 'archived_at'>) {
    return this.http.post<RoleMapping>('/api/role-mappings', payload);
  }

  updateMapping(id: string, payload: Partial<Omit<RoleMapping, 'id' | 'archived_at'>>) {
    return this.http.patch<RoleMapping>(`/api/role-mappings/${id}`, payload);
  }

  disableMapping(id: string) {
    return this.http.post<RoleMapping>(`/api/role-mappings/${id}/disable`, {});
  }

  testExpression(expression: string) {
    return this.http.post<{ matches: boolean }>('/api/role-mappings/test', { expression });
  }
}
