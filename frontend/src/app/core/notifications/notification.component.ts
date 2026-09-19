import { DatePipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynDropdownComponent } from '@synergy-design-system/angular/components/dropdown';
import { NotificationService } from './notification.service';

@Component({
  selector: 'app-notifications',
  imports: [DatePipe, SynBadgeComponent, SynButtonComponent, SynDropdownComponent],
  templateUrl: './notification.component.html',
  styleUrl: './notification.component.scss',
})
export class NotificationComponent {
  readonly notifications = inject(NotificationService);
}
