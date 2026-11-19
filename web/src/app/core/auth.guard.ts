import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';

import { AuthService } from './auth.service';

/** Guards decide whether a route may open. Not logged in -> go to /login. */
export const authGuard: CanMatchFn = () => {
  const auth = inject(AuthService);
  return auth.isLoggedIn() || inject(Router).createUrlTree(['/login']);
};

/** Only managers may open /approvals. The API checks again: this guard is for UX, not security. */
export const managerGuard: CanMatchFn = async () => {
  const auth = inject(AuthService);
  const me = auth.me() ?? (await auth.loadMe().catch(() => null));
  return me?.is_manager || inject(Router).createUrlTree(['/']);
};
