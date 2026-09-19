import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynCardComponent } from '@synergy-design-system/angular/components/card';
import { SynComboboxComponent } from '@synergy-design-system/angular/components/combobox';
import { SynInputComponent } from '@synergy-design-system/angular/components/input';
import { SynOptionComponent } from '@synergy-design-system/angular/components/option';
import { SynSelectComponent } from '@synergy-design-system/angular/components/select';
import { SynSpinnerComponent } from '@synergy-design-system/angular/components/spinner';
import { SynTextareaComponent } from '@synergy-design-system/angular/components/textarea';
import { AuthService } from '../../core/auth/auth.service';
import { Asset, Group } from './asset-catalogue.service';
import { AssetAdministrationService, AssetDraftPayload } from './asset-administration.service';

interface AssetDraft extends AssetDraftPayload {
  id: string | null;
  operational_metadata_text: string;
}

const emptyDraft = (): AssetDraft => ({
  id: null,
  group_id: '',
  asset_type: '',
  name: '',
  description: null,
  operational_metadata: null,
  operational_metadata_text: '',
  remote_host: null,
  remote_url: null,
  operating_system: null,
  access_instructions: null,
  webex_room_id: null,
});

@Component({
  imports: [
    SynAlertComponent,
    SynBadgeComponent,
    SynButtonComponent,
    SynCardComponent,
    SynComboboxComponent,
    SynInputComponent,
    SynOptionComponent,
    SynSelectComponent,
    SynSpinnerComponent,
    SynTextareaComponent,
  ],
  selector: 'app-asset-administration-page',
  styleUrl: './asset-administration.page.scss',
  templateUrl: './asset-administration.page.html',
})
export class AssetAdministrationPage {
  private readonly administration = inject(AssetAdministrationService);
  private readonly auth = inject(AuthService);
  readonly groups = signal<Group[]>([]);
  readonly assets = signal<Asset[]>([]);
  readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  readonly error = signal<string | null>(null);
  readonly draft = signal<AssetDraft>(emptyDraft());
  readonly manageableGroups = computed(() => {
    const roles = this.auth.roles();
    if (roles?.is_owner) return this.groups();
    return this.groups().filter((group) => roles?.group_roles[group.id] === 'group_admin');
  });
  readonly manageableAssets = computed(() => {
    if (this.auth.roles()?.is_owner) return this.assets();
    const groupIds = new Set(this.manageableGroups().map((group) => group.id));
    return this.assets().filter((asset) => groupIds.has(asset.group_id));
  });
  readonly assetTypeSuggestions = computed(() => {
    const groupId = this.draft().group_id;
    const suggestions = new Map<string, string>();
    for (const asset of this.manageableAssets()) {
      if (asset.group_id !== groupId) continue;
      const type = this.normalizeAssetType(asset.asset_type);
      const key = type.toLowerCase();
      if (type && !suggestions.has(key)) suggestions.set(key, type);
    }
    return [...suggestions.values()];
  });
  readonly webexRoomIdSuggestions = computed(() => {
    const groupId = this.draft().group_id;
    const suggestions = new Map<string, string>();
    for (const asset of this.manageableAssets()) {
      if (asset.group_id !== groupId) continue;
      const roomId = asset.webex_room_id?.trim();
      if (roomId && !suggestions.has(roomId)) suggestions.set(roomId, roomId);
    }
    return [...suggestions.values()];
  });

  constructor() {
    this.load();
  }

  load(): void {
    this.state.set('loading');
    this.error.set(null);
    this.administration.groups().subscribe({
      next: ({ items: groups }) => {
        this.groups.set(groups);
        this.administration.list(false).subscribe({
          next: ({ items: active }) =>
            this.administration.list(true).subscribe({
              next: ({ items: archived }) => {
                this.assets.set([...active, ...archived]);
                this.state.set('ready');
              },
              error: (error) => this.loadError(error),
            }),
          error: (error) => this.loadError(error),
        });
      },
      error: (error) => this.loadError(error),
    });
  }

  change(field: keyof Omit<AssetDraft, 'id' | 'operational_metadata'>, value: string): void {
    this.draft.update((draft) => ({ ...draft, [field]: value || null }));
  }

  changeGroup(value: string | number | (string | number)[]): void {
    this.draft.update((draft) => ({ ...draft, group_id: String(value) }));
  }

  changeAssetType(value: string | number | (string | number)[]): void {
    this.change('asset_type', Array.isArray(value) ? String(value[0] ?? '') : String(value));
  }

  changeWebexRoomId(value: string | number | (string | number)[]): void {
    this.change('webex_room_id', Array.isArray(value) ? String(value[0] ?? '') : String(value));
  }

  edit(asset: Asset): void {
    this.draft.set({
      ...asset,
      id: asset.id,
      operational_metadata_text: asset.operational_metadata
        ? JSON.stringify(asset.operational_metadata, null, 2)
        : '',
    });
  }

  save(): void {
    const draft = this.draft();
    if (!draft.name?.trim() || !draft.asset_type?.trim() || (!draft.id && !draft.group_id)) {
      this.error.set('Select a group and enter an asset name and type.');
      return;
    }
    let metadata: Record<string, unknown> | null = null;
    if (draft.operational_metadata_text.trim()) {
      try {
        const parsed: unknown = JSON.parse(draft.operational_metadata_text);
        if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error();
        metadata = parsed as Record<string, unknown>;
      } catch {
        this.error.set('Operational metadata must be a JSON object.');
        return;
      }
    }
    const payload = this.payload(draft, metadata);
    const request = draft.id
      ? this.administration.update(draft.id, this.withoutGroup(payload))
      : this.administration.create(payload);
    request.subscribe({
      next: () => {
        this.draft.set(emptyDraft());
        this.load();
      },
      error: (error) => this.showApiError(error),
    });
  }

  archive(asset: Asset): void {
    this.administration.archive(asset.id).subscribe({
      next: () => this.load(),
      error: (error) => this.showApiError(error),
    });
  }

  reactivate(asset: Asset): void {
    this.administration.reactivate(asset.id).subscribe({
      next: () => this.load(),
      error: (error) => this.showApiError(error),
    });
  }

  groupName(groupId: string): string {
    return this.groups().find((group) => group.id === groupId)?.name ?? 'Unknown group';
  }

  private payload(draft: AssetDraft, metadata: Record<string, unknown> | null): AssetDraftPayload {
    return {
      group_id: draft.group_id,
      asset_type: draft.asset_type.trim(),
      name: draft.name.trim(),
      description: this.nullable(draft.description),
      operational_metadata: metadata,
      remote_host: this.nullable(draft.remote_host),
      remote_url: this.nullable(draft.remote_url),
      operating_system: this.nullable(draft.operating_system),
      access_instructions: this.nullable(draft.access_instructions),
      webex_room_id: this.nullable(draft.webex_room_id),
    };
  }

  private withoutGroup(payload: AssetDraftPayload): Omit<AssetDraftPayload, 'group_id'> {
    return Object.fromEntries(
      Object.entries(payload).filter(([key]) => key !== 'group_id'),
    ) as Omit<AssetDraftPayload, 'group_id'>;
  }

  private nullable(value: string | null): string | null {
    return value?.trim() || null;
  }

  private normalizeAssetType(value: string): string {
    return value.trim().replace(/\s+/g, ' ');
  }

  private loadError(error: unknown): void {
    this.state.set('error');
    this.showApiError(error);
  }

  private showApiError(error: unknown): void {
    const api = error instanceof HttpErrorResponse ? error.error?.error : null;
    this.error.set(api?.message || 'The request could not be completed.');
  }
}
