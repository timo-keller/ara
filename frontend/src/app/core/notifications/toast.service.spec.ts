import { TestBed } from '@angular/core/testing';
import SynAlert from '@synergy-design-system/components/components/alert/alert.js';
import { ToastService } from './toast.service';

describe('ToastService', () => {
  it('shows closable five-second success toasts and treats messages as plain text', () => {
    const alerts: SynAlert[] = [];
    const toast = vi.spyOn(SynAlert.prototype, 'toast').mockImplementation(function (
      this: SynAlert,
    ) {
      alerts.push(this);
      return Promise.resolve();
    });
    try {
      const service = TestBed.inject(ToastService);
      service.success('Reservation cancelled and availability refreshed.');
      service.success('<b>Asset booked</b>');
      expect(alerts).toHaveLength(2);
      expect(alerts[0].variant).toBe('success');
      expect(alerts[0].closable).toBe(true);
      expect(alerts[0].duration).toBe(5000);
      expect(alerts[0].textContent).toBe('Reservation cancelled and availability refreshed.');
      expect(alerts[1].textContent).toBe('<b>Asset booked</b>');
      expect(alerts[1].querySelector('b')).toBeNull();
      expect(alerts[0]).not.toBe(alerts[1]);
      service.error('Only future reservations can be cancelled.');
      expect(alerts[2].variant).toBe('error');
      expect(alerts[2].closable).toBe(true);
      expect(alerts[2].duration).toBe(8000);
      expect(alerts[2].textContent).toBe('Only future reservations can be cancelled.');
    } finally {
      toast.mockRestore();
    }
  });
});
