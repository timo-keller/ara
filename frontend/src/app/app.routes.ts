import { Routes } from '@angular/router';
import {
  assetAdministrationGuard,
  auditGuard,
  authenticatedGuard,
  groupAccessGuard,
  ownerGuard,
} from './core/auth/auth.guard';

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
      import('./features/reservations/reservations.page').then((module) => module.ReservationsPage),
  },
  {
    path: 'assets',
    canActivate: [groupAccessGuard],
    data: { title: 'Assets' },
    loadComponent: () =>
      import('./features/assets/asset-catalogue.page').then((module) => module.AssetCataloguePage),
  },
  {
    path: 'assets/:assetId',
    canActivate: [groupAccessGuard],
    data: { title: 'Asset details' },
    loadComponent: () =>
      import('./features/assets/asset-detail.page').then((module) => module.AssetDetailPage),
  },
  {
    path: 'asset-administration',
    canActivate: [assetAdministrationGuard],
    data: { title: 'Asset administration' },
    loadComponent: () =>
      import('./features/assets/asset-administration.page').then(
        (module) => module.AssetAdministrationPage,
      ),
  },
  {
    path: 'administration',
    canActivate: [ownerGuard],
    data: { title: 'Administration' },
    loadComponent: () =>
      import('./features/administration/administration.page').then(
        (module) => module.AdministrationPage,
      ),
  },
  {
    path: 'audit',
    canActivate: [auditGuard],
    data: { title: 'Audit history' },
    loadComponent: () => import('./features/audit/audit.page').then((module) => module.AuditPage),
  },
];
