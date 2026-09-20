import { CompactModeService } from './compact-mode.service';

describe('CompactModeService', () => {
  beforeEach(() => localStorage.clear());

  it('defaults malformed or absent preferences to normal mode and restores compact mode', () => {
    expect(new CompactModeService().compact()).toBe(false);

    localStorage.setItem('ara.compact-mode', 'not-a-preference');
    expect(new CompactModeService().compact()).toBe(false);

    localStorage.setItem('ara.compact-mode', 'true');
    expect(new CompactModeService().compact()).toBe(true);
  });

  it('keeps the Settings trigger normal while sizing other supported controls in compact mode', () => {
    document.body.innerHTML =
      '<div class="appshell"><syn-button data-compact-mode-exempt></syn-button><syn-button></syn-button><syn-input></syn-input></div>';
    const service = new CompactModeService();
    const [settings, button] = document.querySelectorAll('syn-button');
    const input = document.querySelector('syn-input');

    service.apply();
    expect(settings?.hasAttribute('size')).toBe(false);
    expect(button?.hasAttribute('size')).toBe(false);
    expect(input?.hasAttribute('size')).toBe(false);

    service.setCompact(true);
    service.apply();
    expect(settings?.hasAttribute('size')).toBe(false);
    expect(button?.getAttribute('size')).toBe('small');
    expect(input?.getAttribute('size')).toBe('small');
    expect(localStorage.getItem('ara.compact-mode')).toBe('true');

    service.setCompact(false);
    service.apply();
    expect(settings?.hasAttribute('size')).toBe(false);
    expect(button?.hasAttribute('size')).toBe(false);
    expect(input?.hasAttribute('size')).toBe(false);
  });
});
