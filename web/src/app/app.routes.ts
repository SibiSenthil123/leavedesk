import { Routes } from '@angular/router';

import { authGuard, managerGuard } from './core/auth.guard';
import { LoginPage } from './features/login/login.page';

export const routes: Routes = [
  { path: 'login', component: LoginPage, title: 'Log in · LeaveDesk' },
  {
    path: 'approvals',
    canMatch: [authGuard, managerGuard],
    // Lazy loading: this page's code is only downloaded when a manager opens it.
    loadComponent: () => import('./features/approvals/approvals.page').then((m) => m.ApprovalsPage),
    title: 'Approvals · LeaveDesk',
  },
  {
    path: '',
    canMatch: [authGuard],
    loadComponent: () => import('./features/leave/my-leave.page').then((m) => m.MyLeavePage),
    title: 'My leave · LeaveDesk',
  },
  { path: '**', redirectTo: '' },
];
