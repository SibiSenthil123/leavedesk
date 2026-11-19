import { HttpClient, HttpParams } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { API, Me, Token } from './models';

const TOKEN_KEY = 'leavedesk.token';

/**
 * Who is logged in. State lives in signals: when a signal changes, every
 * screen that reads it updates by itself.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  // The token survives a page reload in sessionStorage (cleared when the tab closes).
  readonly token = signal<string | null>(sessionStorage.getItem(TOKEN_KEY));
  readonly me = signal<Me | null>(null);

  // computed(): a value worked out from other signals, kept up to date automatically.
  readonly isLoggedIn = computed(() => this.token() !== null);
  readonly isManager = computed(() => this.me()?.is_manager ?? false);

  async login(email: string, password: string): Promise<void> {
    // /auth/login expects a FORM (OAuth2 standard), not JSON.
    const body = new HttpParams().set('username', email).set('password', password);
    const token = await firstValueFrom(this.http.post<Token>(`${API}/auth/login`, body));
    this.token.set(token.access_token);
    sessionStorage.setItem(TOKEN_KEY, token.access_token);
    await this.loadMe();
  }

  /** Ask the API who the token belongs to (name, manager or not). */
  async loadMe(): Promise<Me | null> {
    if (!this.token()) return null;
    const me = await firstValueFrom(this.http.get<Me>(`${API}/auth/me`));
    this.me.set(me);
    return me;
  }

  logout(): void {
    this.token.set(null);
    this.me.set(null);
    sessionStorage.removeItem(TOKEN_KEY);
    void this.router.navigate(['/login']);
  }
}
