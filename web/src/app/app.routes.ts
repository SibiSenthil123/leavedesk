import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';
import { LoginPage } from './features/login/login.page';

export const routes: Routes = [
  { path: 'login', component: LoginPage, title: 'Log in · LeaveDesk' },
  // The home page arrives in PR3. For now: logged in -> an empty page under the top bar.
  { path: '', canMatch: [authGuard], children: [] },
  { path: '**', redirectTo: '' },
];
