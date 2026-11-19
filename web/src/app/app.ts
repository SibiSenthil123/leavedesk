import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatToolbarModule } from '@angular/material/toolbar';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from './core/auth.service';

/** The frame around every page: top bar, navigation, and the page itself. */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatToolbarModule, MatButtonModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  readonly auth = inject(AuthService);

  constructor() {
    // A token left from before a page reload: find out who it belongs to.
    if (this.auth.isLoggedIn()) void this.auth.loadMe().catch(() => this.auth.logout());
  }
}
