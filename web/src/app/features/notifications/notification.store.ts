import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { firstValueFrom } from 'rxjs';

import { API, AppNotification, Page } from '../../core/models';

/**
 * The notification bell's data. On login it loads the inbox, then keeps a live
 * line open to the server (Server-Sent Events): new notifications arrive on
 * their own, without the page asking again.
 */
@Injectable({ providedIn: 'root' })
export class NotificationStore {
  private readonly http = inject(HttpClient);
  private readonly snack = inject(MatSnackBar);
  private source: EventSource | null = null;

  private readonly _items = signal<AppNotification[]>([]);
  private readonly _error = signal<string | null>(null);
  readonly items = this._items.asReadonly();
  readonly error = this._error.asReadonly();

  /** The red number on the bell. computed() keeps it right whenever items change. */
  readonly unreadCount = computed(() => this._items().filter((n) => !n.read).length);

  async connect(token: string): Promise<void> {
    this.disconnect();
    try {
      const page = await firstValueFrom(
        this.http.get<Page<AppNotification>>(`${API}/notifications?limit=50`),
      );
      this._items.set(page.items);
      this._error.set(null);
    } catch {
      this._error.set('Could not load notifications');
    }
    // A browser's EventSource cannot send headers, so the token goes in the URL.
    this.source = new EventSource(
      `${API}/notifications/stream?access_token=${encodeURIComponent(token)}`,
    );
    this.source.addEventListener('notification', (event) => {
      this.receive(JSON.parse((event as MessageEvent<string>).data) as AppNotification);
    });
  }

  /** Called for each live message (and by the tests). Newest goes on top. */
  receive(n: AppNotification): void {
    this._items.update((items) => [n, ...items]);
    this.snack.open(n.message, 'OK', { duration: 4000 });
  }

  disconnect(): void {
    this.source?.close(); // close the live line on logout
    this.source = null;
    this._items.set([]);
  }

  /** Opening the panel marks everything read: on screen at once, then on the server. */
  async markAllRead(): Promise<void> {
    if (this.unreadCount() === 0) return;
    this._items.update((items) => items.map((n) => ({ ...n, read: true })));
    await firstValueFrom(this.http.post(`${API}/notifications/read-all`, {})).catch(
      () => undefined,
    );
  }
}
