import { Injectable } from '@angular/core';
import SynAlert from '@synergy-design-system/components/components/alert/alert.js';

@Injectable({ providedIn: 'root' })
export class ToastService {
  success(message: string): void {
    this.show(message, 'success', 5000);
  }

  error(message: string): void {
    this.show(message, 'error', 8000);
  }

  private show(message: string, variant: 'success' | 'error', duration: number): void {
    const alert = new SynAlert();
    alert.variant = variant;
    alert.closable = true;
    alert.duration = duration;
    alert.textContent = message;
    void alert.toast();
  }
}
