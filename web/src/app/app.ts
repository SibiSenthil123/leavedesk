import { Component, effect, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatToolbarModule } from '@angular/material/toolbar';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from './core/auth.service';
import { NotificationBell } from './features/notifications/notification-bell';
import { NotificationStore } from './features/notifications/notification.store';

/** The frame around every page: top bar, navigation, bell, and the page itself. */
@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatToolbarModule,
    MatButtonModule,
    NotificationBell,
  ],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  readonly auth = inject(AuthService);
  private readonly notifications = inject(NotificationStore);

  constructor() {
    // A token left from before a page reload: find out who it belongs to.
    if (this.auth.isLoggedIn()) void this.auth.loadMe().catch(() => this.auth.logout());

    // effect(): runs again whenever a signal it reads changes. Logged in -> open the
    // live notification line; logged out -> close it.
    effect(() => {
      const token = this.auth.token();
      if (token) void this.notifications.connect(token);
      else this.notifications.disconnect();
    });
  }
}
