import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';
import { LoginPage } from './features/login/login.page';

export const routes: Routes = [
  { path: 'login', component: LoginPage, title: 'Log in · LeaveDesk' },
  {
    path: '',
    canMatch: [authGuard],
    // Lazy loading: this page's code is only downloaded when it is opened.
    loadComponent: () => import('./features/leave/my-leave.page').then((m) => m.MyLeavePage),
    title: 'My leave · LeaveDesk',
  },
  { path: '**', redirectTo: '' },
];
