import { Routes } from '@angular/router';
import { authenticatedGuard, groupAccessGuard, ownerGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./features/home/home.page').then((module) => module.HomePage),
    pathMatch: 'full',
  },
  {
    path: 'reservations',
    canActivate: [authenticatedGuard],
    data: { title: 'Reservations' },
    loadComponent: () =>
      import('./features/placeholder/placeholder.page').then((module) => module.PlaceholderPage),
  },
  {
    path: 'assets',
    canActivate: [groupAccessGuard],
    data: { title: 'Assets' },
    loadComponent: () =>
      import('./features/placeholder/placeholder.page').then((module) => module.PlaceholderPage),
  },
  {
    path: 'administration',
    canActivate: [ownerGuard],
    data: { title: 'Administration' },
    loadComponent: () =>
      import('./features/placeholder/placeholder.page').then((module) => module.PlaceholderPage),
  },
];
