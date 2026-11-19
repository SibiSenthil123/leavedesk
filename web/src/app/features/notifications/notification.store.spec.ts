import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AppNotification } from '../../core/models';
import { NotificationStore } from './notification.store';

const note = (id: string, read = false): AppNotification => ({
  id,
  event: 'submitted',
  request_id: 'r1',
  message: `message ${id}`,
  read,
  created_at: '2026-11-19T10:00:00Z',
});

describe('NotificationStore', () => {
  let store: NotificationStore;
  let backend: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    store = TestBed.inject(NotificationStore);
    backend = TestBed.inject(HttpTestingController);
  });

  it('counts unread notifications as new ones arrive', () => {
    expect(store.unreadCount()).toBe(0);
    store.receive(note('a'));
    store.receive(note('b', true));
    store.receive(note('c'));
    expect(store.unreadCount()).toBe(2);
    expect(store.items()[0].id).toBe('c'); // newest on top
  });

  it('opening the panel marks everything read', async () => {
    store.receive(note('a'));
    const done = store.markAllRead();
    expect(store.unreadCount()).toBe(0); // instantly on screen
    backend.expectOne('/api/notifications/read-all').flush({ marked_read: 1 });
    await done;
  });
});
