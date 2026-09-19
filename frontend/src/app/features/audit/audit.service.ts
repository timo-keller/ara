import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

export interface AuditFilters {
  groupId: string;
  actorId: string;
  action: string[];
  targetType: string[];
  targetId: string;
  createdAtFrom: string;
  createdAtTo: string;
  offset: number;
  limit: number;
}

export interface AuditEvent {
  id: string;
  actor_id: string | null;
  group_id: string | null;
  action: string;
  target_type: string;
  target_id: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  correlation_id: string | null;
  created_at: string;
}

export interface AuditPage {
  items: AuditEvent[];
  total: number;
  offset: number;
  limit: number;
}

const queryNames = {
  groupId: 'group_id',
  actorId: 'actor_id',
  targetId: 'target_id',
  createdAtFrom: 'created_at_from',
  createdAtTo: 'created_at_to',
} as const;

export const defaultAuditFilters = (): AuditFilters => ({
  groupId: '',
  actorId: '',
  action: [],
  targetType: [],
  targetId: '',
  createdAtFrom: '',
  createdAtTo: '',
  offset: 0,
  limit: 25,
});

export function auditQuery(filters: AuditFilters): HttpParams {
  let params = new HttpParams().set('offset', filters.offset).set('limit', filters.limit);
  for (const [key, name] of Object.entries(queryNames) as [keyof typeof queryNames, string][]) {
    const value = filters[key].trim();
    if (value) params = params.set(name, value);
  }
  for (const action of filters.action) params = params.append('action', action);
  for (const targetType of filters.targetType) params = params.append('target_type', targetType);
  return params;
}

@Injectable({ providedIn: 'root' })
export class AuditService {
  private readonly http = inject(HttpClient);

  list(filters: AuditFilters) {
    return this.http.get<AuditPage>('/api/audit-events', { params: auditQuery(filters) });
  }
}
