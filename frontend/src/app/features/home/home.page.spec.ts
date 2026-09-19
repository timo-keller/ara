import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { HomePage } from './home.page';

describe('HomePage', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomePage],
    }).compileComponents();
  });

  it('renders an accessible Synergy button without runtime warnings', () => {
    const warning = vi.spyOn(console, 'warn');
    const fixture = TestBed.createComponent(HomePage);

    fixture.detectChanges();

    const button = fixture.nativeElement.querySelector('syn-button');
    const icon = fixture.nativeElement.querySelector('syn-icon');

    expect(button?.textContent).toContain('Create reservation');
    expect(icon?.getAttribute('aria-hidden')).toBe('true');
    expect(warning).not.toHaveBeenCalled();

    warning.mockRestore();
  });
});
