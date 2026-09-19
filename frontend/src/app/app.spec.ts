import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { App } from './app';
import { routes } from './app.routes';

class ResizeObserverStub {
  disconnect(): undefined {
    return undefined;
  }
  observe(): undefined {
    return undefined;
  }
  unobserve(): undefined {
    return undefined;
  }
}

interface HeaderElement extends HTMLElement {
  connectSideNavigation(sideNav: HTMLElement): void;
}

describe('App', () => {
  beforeEach(async () => {
    globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter(routes)],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('renders the Synergy rail shell and owner navigation from effective roles', () => {
    const headerElement = customElements.get('syn-header') as unknown as {
      prototype: HeaderElement;
    };
    const connectSideNavigation = vi.spyOn(headerElement.prototype, 'connectSideNavigation');
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/auth/session').flush({
      authenticated: true,
      user: { id: 'user-id', display_name: 'Ada', email: 'ada@example.test' },
      roles: { is_owner: true, group_roles: {} },
    });
    fixture.detectChanges();

    const rail = fixture.nativeElement.querySelector('syn-side-nav');
    expect(rail?.getAttribute('variant')).toBe('rail');
    expect(connectSideNavigation).toHaveBeenCalledWith(rail);
    expect(fixture.nativeElement.textContent).toContain('Effective roles: Owner');
    expect(fixture.nativeElement.textContent).toContain('Administration');
    http.verify();
  });
});
