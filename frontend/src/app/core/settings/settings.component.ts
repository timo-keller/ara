import { Component, inject } from '@angular/core';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynDropdownComponent } from '@synergy-design-system/angular/components/dropdown';
import { SynIconComponent } from '@synergy-design-system/angular/components/icon';
import { SynSwitchComponent } from '@synergy-design-system/angular/components/switch';
import { NotificationComponent } from '../notifications/notification.component';
import { NotificationService } from '../notifications/notification.service';
import { CompactModeService } from './compact-mode.service';

@Component({
  selector: 'app-settings',
  imports: [
    NotificationComponent,
    SynBadgeComponent,
    SynButtonComponent,
    SynDropdownComponent,
    SynIconComponent,
    SynSwitchComponent,
  ],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
})
export class SettingsComponent {
  readonly compactMode = inject(CompactModeService);
  readonly notifications = inject(NotificationService);

  accessibleLabel(): string {
    const unreadCount = this.notifications.unreadCount();
    if (unreadCount === 0) return 'Settings';
    return `Settings, ${unreadCount} unread notification${unreadCount === 1 ? '' : 's'}`;
  }
}
