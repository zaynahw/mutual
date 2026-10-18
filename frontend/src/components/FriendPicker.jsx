import { useEffect, useState } from 'react';
import { api } from '../api.js';
import './FriendPicker.css';

function getInitials(name) {
  return name
    .replace(/\s*\([^)]*\)\s*/g, ' ')
    .trim()
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

function FriendPicker({ currentUserId, selectedFriendId, onSelect }) {
  const [friends, setFriends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    api.getFriends(currentUserId)
      .then((result) => { if (active) setFriends(result.filter((friend) => friend.id !== currentUserId)); })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : 'Could not load friends.'); })
      .finally(() => { if (active) setLoading(false); });

    return () => { active = false; };
  }, [currentUserId, retry]);

  const showSearch = friends.length > 5;
  const visibleFriends = showSearch
    ? friends.filter((friend) => friend.display_name.toLowerCase().includes(query.trim().toLowerCase()))
    : friends;

  return <section className="friend-picker" aria-labelledby="friend-picker-title">
    <h2 id="friend-picker-title" className="friend-picker__title">Choose a friend</h2>
    {showSearch && <label className="friend-picker__search">Search friends<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by name" /></label>}
    {loading ? <p className="friend-picker__state" role="status">Loading friends…</p>
      : error ? <div className="friend-picker__state" role="alert"><p>{error}</p><button type="button" onClick={() => setRetry((attempt) => attempt + 1)}>Retry</button></div>
        : friends.length === 0 ? <p className="friend-picker__state">No friends yet</p>
          : visibleFriends.length === 0 ? <p className="friend-picker__state" role="status">No matching friends</p>
            : <div className="friend-picker__list">
              {visibleFriends.map((friend) => <button
                type="button"
                className={`friend-picker__card${friend.id === selectedFriendId ? ' selected' : ''}`}
                aria-pressed={friend.id === selectedFriendId}
                onClick={() => onSelect(friend)}
                key={friend.id}
              >
                <span className="friend-picker__avatar" aria-hidden="true">{getInitials(friend.display_name)}</span>
                <span className="friend-picker__name">{friend.display_name}</span>
              </button>)}
            </div>}
  </section>;
}

export default FriendPicker;