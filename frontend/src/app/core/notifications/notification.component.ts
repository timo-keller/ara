import { DatePipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { NotificationService } from './notification.service';

@Component({
  selector: 'app-notifications',
  imports: [DatePipe, SynButtonComponent],
  templateUrl: './notification.component.html',
  styleUrl: './notification.component.scss',
})
export class NotificationComponent {
  readonly notifications = inject(NotificationService);
}
