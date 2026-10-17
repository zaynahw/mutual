import type { ComponentType } from 'react';
import type { Friend } from '../api.js';

declare const FriendPicker: ComponentType<{
  currentUserId: string;
  selectedFriendId: string | null;
  onSelect: (friend: Friend) => void;
}>;

export default FriendPicker;