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

  it('uses documented small sizes only while compact mode is enabled', () => {
    document.body.innerHTML =
      '<div class="appshell"><syn-button></syn-button><syn-input></syn-input></div>';
    const service = new CompactModeService();

    service.setCompact(true);
    service.apply();
    expect(document.querySelector('syn-button')?.getAttribute('size')).toBe('small');
    expect(document.querySelector('syn-input')?.getAttribute('size')).toBe('small');
    expect(localStorage.getItem('ara.compact-mode')).toBe('true');

    service.setCompact(false);
    service.apply();
    expect(document.querySelector('syn-button')?.hasAttribute('size')).toBe(false);
    expect(document.querySelector('syn-input')?.hasAttribute('size')).toBe(false);
  });
});
