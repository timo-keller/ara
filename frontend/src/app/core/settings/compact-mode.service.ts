import { Injectable, signal } from '@angular/core';

const STORAGE_KEY = 'ara.compact-mode';
const COMPACT_SIZED_SELECTOR = [
  'syn-button',
  'syn-icon-button',
  'syn-input',
  'syn-select',
  'syn-combobox',
  'syn-pagination',
  'syn-switch',
  'syn-textarea',
].join(', ');

@Injectable({ providedIn: 'root' })
export class CompactModeService {
  readonly compact = signal(this.readPreference());

  setCompact(compact: boolean): void {
    this.compact.set(compact);
    try {
      localStorage.setItem(STORAGE_KEY, String(compact));
    } catch {
      // Storage can be unavailable (for example, in a private browsing context).
    }
  }

  apply(): void {
    const shell = document.querySelector('.appshell');
    if (!shell) return;

    if (this.compact()) {
      shell
        .querySelectorAll<HTMLElement>(`${COMPACT_SIZED_SELECTOR}:not([size])`)
        .forEach((element) => {
          element.setAttribute('size', 'small');
          element.dataset['compactModeSized'] = '';
        });
      return;
    }

    shell.querySelectorAll<HTMLElement>('[data-compact-mode-sized]').forEach((element) => {
      element.removeAttribute('size');
      delete element.dataset['compactModeSized'];
    });
  }

  private readPreference(): boolean {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  }
}
