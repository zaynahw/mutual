import React from 'react';
import { listFriendRequests, removeFriendship, respondToFriendRequest, sendFriendRequest } from '../lib/api';
import type { FriendRequest, PublicUser } from '../lib/api';
import { activeRequestFor } from '../lib/friendships';

interface Props {
  currentUser: PublicUser;
  users: PublicUser[];
}

export function Friendships({ currentUser, users }: Props) {
  const [requests, setRequests] = React.useState<FriendRequest[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState('');
  const [actionError, setActionError] = React.useState('');
  const [notice, setNotice] = React.useState('');
  const [confirmRemoveId, setConfirmRemoveId] = React.useState<string | null>(null);
  const [working, setWorking] = React.useState(false);
  const [reload, setReload] = React.useState(0);
  const pendingAction = React.useRef<AbortController | null>(null);

  React.useEffect(() => () => pendingAction.current?.abort(), []);
  React.useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError('');
    listFriendRequests(currentUser.id, controller.signal).then(data => {
      if (!controller.signal.aborted) setRequests(data);
    }).catch(() => {
      if (!controller.signal.aborted) setLoadError('Could not load friend requests. Check the backend and retry.');
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [currentUser.id, reload]);

  async function act(
    action: (signal: AbortSignal) => Promise<FriendRequest>, message: string,
  ) {
    if (pendingAction.current || loading || loadError) return;
    const controller = new AbortController();
    pendingAction.current = controller;
    setWorking(true);
    setActionError('');
    setNotice('');
    try {
      const updated = await action(controller.signal);
      if (!controller.signal.aborted) {
        setRequests(previous => [...previous.filter(request => request.id !== updated.id), updated]);
        setNotice(message);
        setConfirmRemoveId(null);
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setActionError(error instanceof TypeError
          ? 'Could not reach the backend. Refresh requests before retrying; your action may have completed.'
          : error instanceof Error ? error.message : 'Could not update friendship.');
      }
    } finally {
      if (!controller.signal.aborted) {
        pendingAction.current = null;
        setWorking(false);
      }
    }
  }

  const name = (id: string) => users.find(user => user.id === id)?.display_name ?? 'Unknown demo user';
  const incoming = requests.filter(request => request.status === 'pending' && request.recipient_id === currentUser.id);
  const outgoing = requests.filter(request => request.status === 'pending' && request.sender_id === currentUser.id);
  const friends = requests.filter(request => request.status === 'accepted');
  const history = requests.filter(request => request.status === 'declined' || request.status === 'removed');
  const otherId = (request: FriendRequest) => request.sender_id === currentUser.id ? request.recipient_id : request.sender_id;
  const unavailable = working || loading || Boolean(loadError);

  function responseButtons(request: FriendRequest) {
    return <div className="mt-2 flex gap-4">
      <button disabled={unavailable} className="text-teal-800 underline disabled:opacity-50"
        onClick={() => act(signal => respondToFriendRequest(currentUser.id, request.id, 'accept', signal), 'Friend request accepted.')}>
        Accept
      </button>
      <button disabled={unavailable} className="text-stone-600 underline disabled:opacity-50"
        onClick={() => act(signal => respondToFriendRequest(currentUser.id, request.id, 'decline', signal), 'Friend request declined.')}>
        Decline
      </button>
    </div>;
  }

  return (
    <section aria-label="Friendships" className="space-y-6 rounded-xl border border-stone-200 bg-white p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Friendships</h2>
          <p className="mt-2 text-sm text-stone-600">Send requests as {currentUser.display_name}. Switch demo users to respond as the recipient.</p>
        </div>
        <button disabled={working || loading} onClick={() => setReload(value => value + 1)} className="underline disabled:opacity-50">Refresh requests</button>
      </div>
      <p className="text-sm text-stone-500">Accepted friendships are saved. Shared schedule browsing and selected-friends window controls are coming next.</p>
      {loading && <p role="status">Loading friendships…</p>}
      {loadError && <p role="alert" className="text-red-700">{loadError}</p>}
      {actionError && <p role="alert" className="text-red-700">{actionError}</p>}
      {notice && <p role="status" className="text-teal-800">{notice}</p>}
      {!loading && !loadError && <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-3">
          <h3 className="text-lg font-medium">Find friends</h3>
          <ul className="space-y-3">
            {users.filter(user => user.id !== currentUser.id).map(user => {
              const active = activeRequestFor(requests, currentUser.id, user.id);
              return <li key={user.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-stone-200 p-3">
                <span>{user.display_name}</span>
                {active ? <span className="text-sm text-stone-600">
                  {active.status === 'accepted' ? 'Friends' : active.sender_id === currentUser.id ? 'Request sent' : 'Incoming request'}
                </span> : <button disabled={unavailable} className="text-teal-800 underline disabled:opacity-50"
                  onClick={() => act(signal => sendFriendRequest(currentUser.id, user.id, signal), 'Friend request sent.')}>
                  Add friend
                </button>}
              </li>;
            })}
          </ul>
          {users.filter(user => user.id !== currentUser.id).length === 0 && <p>No other demo users.</p>}
        </div>
        <div className="space-y-5">
          <div>
            <h3 className="text-lg font-medium">Incoming requests</h3>
            {incoming.length === 0 ? <p className="text-sm text-stone-500">No incoming requests.</p> : <ul className="space-y-3">
              {incoming.map(request => <li key={request.id} className="rounded-lg border border-stone-200 p-3">
                <p>{name(request.sender_id)}</p>{responseButtons(request)}
              </li>)}
            </ul>}
          </div>
          <div>
            <h3 className="text-lg font-medium">Outgoing requests</h3>
            {outgoing.length === 0 ? <p className="text-sm text-stone-500">No outgoing requests.</p> : <ul>
              {outgoing.map(request => <li key={request.id}>{name(request.recipient_id)} · Pending</li>)}
            </ul>}
          </div>
          <div>
            <h3 className="text-lg font-medium">Friends</h3>
            {friends.length === 0 ? <p className="text-sm text-stone-500">No accepted friends yet.</p> : <ul>
              {friends.map(request => <li key={request.id} className="space-y-2 rounded-lg border border-stone-200 p-3">
                <p>{name(otherId(request))}</p>
                <button disabled={unavailable} className="text-red-700 underline disabled:opacity-50"
                  onClick={() => { setConfirmRemoveId(request.id); setActionError(''); }}>
                  Remove friend
                </button>
                {confirmRemoveId === request.id && <div className="rounded border border-red-200 bg-red-50 p-3">
                  <p>Remove {name(otherId(request))} as a friend? Reconnecting requires a new accepted request.</p>
                  <button disabled={unavailable} className="mt-2 mr-4 text-red-800 underline"
                    onClick={() => act(signal => removeFriendship(currentUser.id, request.id, signal), 'Friendship removed. You can send a new request.')}>
                    Confirm removal
                  </button>
                  <button disabled={unavailable} className="underline" onClick={() => setConfirmRemoveId(null)}>Keep friendship</button>
                </div>}
              </li>)}
            </ul>}
          </div>
          <details>
            <summary className="cursor-pointer">Relationship history ({history.length})</summary>
            {history.length === 0 ? <p className="text-sm text-stone-500">No past requests or friendships.</p> : <ul>
              {history.map(request => <li key={request.id}>{name(otherId(request))} · {request.status === 'removed' ? 'Removed' : 'Declined'}</li>)}
            </ul>}
          </details>
        </div>
      </div>}
    </section>
  );
}
