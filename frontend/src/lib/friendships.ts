import type { FriendRequest } from './api';

/** Active relationship wins over any older declined/removed history, in either direction. */
export function activeRequestFor(
  requests: FriendRequest[], currentUserId: string, otherUserId: string,
): FriendRequest | undefined {
  return requests.find(request => (request.status === 'pending' || request.status === 'accepted') && (
    (request.sender_id === currentUserId && request.recipient_id === otherUserId) ||
    (request.sender_id === otherUserId && request.recipient_id === currentUserId)
  ));
}
