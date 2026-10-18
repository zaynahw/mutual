import type { Dispatch, FormEvent, SetStateAction } from 'react';
import type { Activity, SocialWindowInput, PublicUser } from '../lib/api';

const activities: Activity[] = ['coffee', 'meal', 'walk', 'study', 'concert'];
type Setter<T> = Dispatch<SetStateAction<T>>;

interface Props {
  friends: PublicUser[];
  selectedFriends: string[];
  setSelectedFriends: Setter<string[]>;
  editingId: string | null;
  saving: boolean;
  start: string;
  end: string;
  chosen: Activity[];
  audience: SocialWindowInput['visibility']['audience'];
  mode: SocialWindowInput['sharing_mode'];
  error: string;
  notice: string;
  setStart: Setter<string>;
  setEnd: Setter<string>;
  setChosen: Setter<Activity[]>;
  setAudience: Setter<SocialWindowInput['visibility']['audience']>;
  setMode: Setter<SocialWindowInput['sharing_mode']>;
  onSubmit: (event: FormEvent) => void;
  onCancel: () => void;
}

export function SocialWindowForm({
  friends, selectedFriends, setSelectedFriends, editingId, saving, start, end, chosen, audience, mode, error, notice,
  setStart, setEnd, setChosen, setAudience, setMode, onSubmit, onCancel,
}: Props) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <h3 className="text-lg font-medium">{editingId ? 'Edit window' : 'Add a window'}</h3>
      <fieldset disabled={saving} className="space-y-4">
        <label className="block">
          Start
          <input type="datetime-local" required value={start} onChange={event => setStart(event.target.value)} className="mt-1 block w-full rounded border border-stone-300 p-2" />
        </label>
        <label className="block">
          End
          <input type="datetime-local" required value={end} onChange={event => setEnd(event.target.value)} className="mt-1 block w-full rounded border border-stone-300 p-2" />
        </label>
        <fieldset>
          <legend className="mb-2">Activities</legend>
          <div className="flex flex-wrap gap-4">
            {activities.map(activity => (
              <label key={activity} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={chosen.includes(activity)}
                  onChange={event => setChosen(values => event.target.checked
                    ? [...values, activity]
                    : values.filter(value => value !== activity))}
                />
                {activity}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="block">
          Audience
          <select value={audience} onChange={event => setAudience(event.target.value as typeof audience)} className="mt-1 block w-full rounded border border-stone-300 p-2">
            <option value="private">Private</option>
            <option value="community">Georgia Tech community</option>
            <option value="friends">Accepted friends</option>
            <option value="selected_friends">Selected accepted friends</option>
          </select>
        </label>
        <p className="text-sm text-stone-500">Private windows cannot match another person. Other audiences are checked by the backend for schedule browsing and matching.</p>
        {audience === 'selected_friends' && <fieldset>
          <legend>Choose accepted friends</legend>
          {friends.length === 0 && <p>No accepted friends yet. Add one in People, then return here.</p>}
          {friends.map(friend => <label className="flex items-center gap-2" key={friend.id}><input type="checkbox" checked={selectedFriends.includes(friend.id)} onChange={e => setSelectedFriends(old => e.target.checked ? [...old,friend.id] : old.filter(id => id !== friend.id))} />{friend.display_name}</label>)}
          {selectedFriends.filter(id => !friends.some(friend => friend.id === id)).map(id => <label className="flex items-center gap-2 text-red-700" key={id}><input type="checkbox" checked onChange={() => setSelectedFriends(old => old.filter(value => value !== id))} />{id}: no longer an accepted friend; uncheck before saving</label>)}
        </fieldset>}

        <label className="block">
          Sharing mode
          <select value={mode} onChange={event => setMode(event.target.value as typeof mode)} className="mt-1 block w-full rounded border border-stone-300 p-2">
            <option value="visible">Visible on shared schedule</option>
            <option value="matching_only">Use for matching; hide from shared schedule</option>
          </select>
        </label>
        <button type="submit" className="rounded-lg bg-teal-800 px-4 py-3 text-white disabled:opacity-60">
          {saving ? 'Working…' : editingId ? 'Save changes' : 'Save social window'}
        </button>
        {editingId && <button type="button" onClick={onCancel} className="ml-3 underline">Cancel editing</button>}
      </fieldset>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {notice && <p role="status" className="text-teal-800">{notice}</p>}
    </form>
  );
}
