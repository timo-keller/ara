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

  it('immediately sizes controls and restores their original documented size while keeping Settings normal', () => {
    document.body.innerHTML =
      '<div class="appshell"><syn-button data-compact-mode-exempt></syn-button><syn-button size="medium"></syn-button><syn-input></syn-input></div>';
    const service = new CompactModeService();
    const [settings, button] = document.querySelectorAll('syn-button');
    const input = document.querySelector('syn-input');

    expect(settings?.hasAttribute('size')).toBe(false);
    expect(button?.getAttribute('size')).toBe('medium');
    expect(input?.hasAttribute('size')).toBe(false);

    service.setCompact(true);
    expect(settings?.hasAttribute('size')).toBe(false);
    expect(button?.getAttribute('size')).toBe('small');
    expect(input?.getAttribute('size')).toBe('small');
    expect(localStorage.getItem('ara.compact-mode')).toBe('true');

    service.setCompact(false);
    expect(settings?.hasAttribute('size')).toBe(false);
    expect(button?.getAttribute('size')).toBe('medium');
    expect(input?.hasAttribute('size')).toBe(false);
  });

  it('applies a saved preference and sizes controls rendered after compact mode is enabled', () => {
    localStorage.setItem('ara.compact-mode', 'true');
    document.body.innerHTML = '<div class="appshell"><syn-button></syn-button></div>';
    const service = new CompactModeService();

    service.apply();
    expect(document.querySelector('syn-button')?.getAttribute('size')).toBe('small');

    document.querySelector('.appshell')?.insertAdjacentHTML('beforeend', '<syn-input></syn-input>');
    service.apply();
    expect(document.querySelector('syn-input')?.getAttribute('size')).toBe('small');
  });
});
