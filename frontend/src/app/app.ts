import { Component, ViewChild, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynHeaderComponent } from '@synergy-design-system/angular/components/header';
import { SynIconComponent } from '@synergy-design-system/angular/components/icon';
import { SynNavItemComponent } from '@synergy-design-system/angular/components/nav-item';
import { SynSideNavComponent } from '@synergy-design-system/angular/components/side-nav';
import { filter } from 'rxjs';
import { AuthService } from './core/auth/auth.service';

@Component({
  imports: [
    RouterOutlet,
    SynButtonComponent,
    SynHeaderComponent,
    SynIconComponent,
    SynNavItemComponent,
    SynSideNavComponent,
  ],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  private header?: SynHeaderComponent;
  private sideNav?: SynSideNavComponent;

  @ViewChild(SynHeaderComponent)
  set railHeader(header: SynHeaderComponent | undefined) {
    this.header = header;
    this.connectRailNavigation();
  }

  @ViewChild(SynSideNavComponent)
  set railSideNav(sideNav: SynSideNavComponent | undefined) {
    this.sideNav = sideNav;
    this.connectRailNavigation();
  }

  readonly currentUrl = signal('/');

  readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  constructor() {
    this.router.events
      .pipe(filter((event) => event instanceof NavigationEnd))
      .subscribe((event) => {
        this.currentUrl.set(event.urlAfterRedirects);
      });
    this.auth.loadSession().subscribe();
  }

  private connectRailNavigation(): void {
    if (this.header && this.sideNav) {
      this.header.nativeElement.connectSideNavigation(this.sideNav.nativeElement);
    }
  }

  navigate(path: string, event: Event): void {
    event.preventDefault();
    void this.router.navigateByUrl(path);
  }

  isCurrent(path: string): boolean {
    return this.currentUrl() === path;
  }

  roleLabels(): string[] {
    const roles = this.auth.roles();
    if (!roles) return [];
    const groupRoles = Object.entries(roles.group_roles).map(
      ([groupId, role]) => `Group ${role} (${groupId})`,
    );
    return roles.is_owner ? ['Owner', ...groupRoles] : groupRoles;
  }

  logout(event: Event): void {
    event.preventDefault();
    this.auth.logout().subscribe(() => void this.router.navigateByUrl('/'));
  }
}
