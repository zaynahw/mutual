import type { SocialWindow } from '../lib/api';

interface Props {
  windows: SocialWindow[];
  loading: boolean;
  listError: string;
  saving: boolean;
  confirmDeleteId: string | null;
  timezone: string;
  onRetry: () => void;
  onEdit: (window: SocialWindow) => void;
  onRequestDelete: (id: string) => void;
  onConfirmDelete: (id: string) => void;
  onCancelDelete: () => void;
}

export function SocialWindowList({
  windows, loading, listError, saving, confirmDeleteId, timezone,
  onRetry, onEdit, onRequestDelete, onConfirmDelete, onCancelDelete,
}: Props) {
  const formatter = new Intl.DateTimeFormat(undefined, {
    timeZone: timezone, dateStyle: 'medium', timeStyle: 'short',
  });
  const displayTime = (value: string) => formatter.format(new Date(value));

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">Saved windows</h3>
      {loading ? (
        <p role="status">Loading windows…</p>
      ) : listError ? (
        <div role="alert">
          <p className="text-red-700">{listError}</p>
          <button onClick={onRetry} className="mt-2 underline">Retry loading windows</button>
        </div>
      ) : windows.length === 0 ? (
        <p>No social windows yet.</p>
      ) : (
        <ul className="space-y-3">
          {windows.map(window => (
            <li key={window.id} className="space-y-2 rounded-lg border border-stone-200 p-4">
              <p className="font-medium">{window.allowed_activities.join(', ')}</p>
              <p className="text-sm">{displayTime(window.start)} → {displayTime(window.end)}</p>
              <p className="text-sm text-stone-600">
                {window.visibility.audience.replaceAll('_', ' ')} · {window.sharing_mode === 'matching_only' ? 'Matching only' : 'Visible'}
              </p>
              <div className="flex gap-4">
                <button
                  disabled={saving || window.visibility.audience === 'selected_friends'}
                  onClick={() => onEdit(window)}
                  className="text-teal-800 underline disabled:opacity-50"
                >Edit</button>
                <button disabled={saving} onClick={() => onRequestDelete(window.id)} className="text-red-700 underline disabled:opacity-50">
                  Delete
                </button>
              </div>
              {window.visibility.audience === 'selected_friends' && (
                <p className="text-xs text-stone-500">Editing requires friendship setup.</p>
              )}
              {confirmDeleteId === window.id && (
                <div className="rounded border border-red-200 bg-red-50 p-3">
                  <p>Delete this social window? This cannot be undone.</p>
                  <button disabled={saving} onClick={() => onConfirmDelete(window.id)} className="mt-2 mr-4 font-medium text-red-800 underline">
                    Confirm delete
                  </button>
                  <button disabled={saving} onClick={onCancelDelete} className="underline">Keep window</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
