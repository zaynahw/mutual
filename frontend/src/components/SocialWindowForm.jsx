import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { localDateTimeToISO } from './socialWindowTime.js';
import './SocialWindowForm.css';

const activities = ['Coffee', 'Meal', 'Hiking', 'Games', 'Movie', 'Study'];

function SocialWindowForm({ userId, timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone, onCreated }) {
  const [date, setDate] = useState('2026-10-19');
  const [startTime, setStartTime] = useState('18:00');
  const [endTime, setEndTime] = useState('21:00');
  const [activityTypes, setActivityTypes] = useState(['coffee', 'hiking']);
  const [visibility, setVisibility] = useState('specific');
  const [selectedFriendIds, setSelectedFriendIds] = useState([]);
  const [friends, setFriends] = useState([]);
  const [friendsLoading, setFriendsLoading] = useState(true);
  const [friendsError, setFriendsError] = useState('');
  const [friendsRetry, setFriendsRetry] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [failedWindow, setFailedWindow] = useState(null);
  const [success, setSuccess] = useState('');

  useEffect(() => {
    let active = true;
    setFriendsLoading(true);
    setFriendsError('');
    api.getFriends(userId)
      .then((result) => {
        if (active) setFriends(result.filter((friend) => friend.id !== userId));
      })
      .catch((cause) => {
        if (active) setFriendsError(cause instanceof Error ? cause.message : 'Could not load friends.');
      })
      .finally(() => {
        if (active) setFriendsLoading(false);
      });

    return () => { active = false; };
  }, [userId, friendsRetry]);

  const visibleFriendIds = visibility === 'everyone'
    ? friends.map((friend) => friend.id)
    : selectedFriendIds.filter((id) => friends.some((friend) => friend.id === id));
  let dateTimeError = '';
  if (date && startTime && endTime && endTime > startTime) {
    try {
      localDateTimeToISO(date, startTime, timeZone);
      localDateTimeToISO(date, endTime, timeZone);
    } catch (cause) {
      dateTimeError = cause instanceof Error ? cause.message : 'Enter a valid local time.';
    }
  }
  const errors = {
    date: date ? '' : 'Choose a date.',
    startTime: startTime ? '' : 'Choose a start time.',
    endTime: !endTime ? 'Choose an end time.' : startTime && endTime <= startTime ? 'End time must be after start time.' : '',
    activityTypes: activityTypes.length ? '' : 'Choose at least one activity.',
    visibility: friendsLoading || friendsError || visibleFriendIds.length ? '' : 'Choose at least one person who can see this window.',
    dateTime: dateTimeError,
  };
  const isValid = !friendsLoading && !friendsError && Object.values(errors).every((error) => !error);

  function clearResult() {
    setSubmitError('');
    setFailedWindow(null);
    setSuccess('');
  }

  function toggleActivity(activity) {
    clearResult();
    setActivityTypes((current) => current.includes(activity)
      ? current.filter((item) => item !== activity)
      : [...current, activity]);
  }

  function toggleFriend(friendId) {
    clearResult();
    setSelectedFriendIds((current) => current.includes(friendId)
      ? current.filter((id) => id !== friendId)
      : [...current, friendId]);
  }

  function resetForm() {
    setDate('2026-10-19');
    setStartTime('18:00');
    setEndTime('21:00');
    setActivityTypes(['coffee', 'hiking']);
    setVisibility('specific');
    setSelectedFriendIds(friends.length ? [friends[0].id] : []);
  }

  async function submitWindow(window) {
    setSubmitting(true);
    setSubmitError('');
    setSuccess('');
    try {
      const created = await api.createSocialWindow(window);
      resetForm();
      setFailedWindow(null);
      setSuccess('Availability saved.');
      onCreated?.(created);
    } catch (cause) {
      setFailedWindow(window);
      setSubmitError(cause instanceof Error ? cause.message : 'Could not save this availability window.');
    } finally {
      setSubmitting(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (!isValid || submitting) return;

    const window = {
      user_id: userId,
      start: localDateTimeToISO(date, startTime, timeZone),
      end: localDateTimeToISO(date, endTime, timeZone),
      visible_to: visibleFriendIds,
      activity_types: activityTypes,
    };
    submitWindow(window);
  }

  return <form className="social-window-form" onSubmit={handleSubmit} data-user-id={userId}>
    <div className="social-window-form__heading">
      <h2>Set a social window</h2>
      <p>Share a time you’re open to making plans.</p>
    </div>

    <div className="social-window-form__date-time">
      <label className="social-window-form__field">
        <span>Date</span>
        <input type="date" value={date} onChange={(event) => { setDate(event.target.value); clearResult(); }} aria-invalid={Boolean(errors.date)} />
        {errors.date && <span className="social-window-form__error">{errors.date}</span>}
      </label>
      <label className="social-window-form__field">
        <span>Start time</span>
        <input type="time" value={startTime} onChange={(event) => { setStartTime(event.target.value); clearResult(); }} aria-invalid={Boolean(errors.startTime)} />
        {errors.startTime && <span className="social-window-form__error">{errors.startTime}</span>}
      </label>
      <label className="social-window-form__field">
        <span>End time</span>
        <input type="time" value={endTime} onChange={(event) => { setEndTime(event.target.value); clearResult(); }} aria-invalid={Boolean(errors.endTime)} />
        {errors.endTime && <span className="social-window-form__error">{errors.endTime}</span>}
      </label>
    </div>

    <fieldset className="social-window-form__group">
      <legend>What would you like to do?</legend>
      <div className="social-window-form__activity-list">
        {activities.map((activity) => <label className="social-window-form__choice" key={activity}>
          <input type="checkbox" name="activity" value={activity.toLowerCase()} checked={activityTypes.includes(activity.toLowerCase())} onChange={() => toggleActivity(activity.toLowerCase())} />
          <span>{activity}</span>
        </label>)}
      </div>
      {errors.activityTypes && <span className="social-window-form__error">{errors.activityTypes}</span>}
      {errors.dateTime && <span className="social-window-form__error">{errors.dateTime}</span>}
    </fieldset>

    <fieldset className="social-window-form__group">
      <legend>Who can see this window?</legend>
      <div className="social-window-form__visibility-options">
        <label className="social-window-form__radio"><input type="radio" name="visibility" value="everyone" checked={visibility === 'everyone'} onChange={() => { setVisibility('everyone'); clearResult(); }} /><span>Everyone</span></label>
        <label className="social-window-form__radio"><input type="radio" name="visibility" value="specific" checked={visibility === 'specific'} onChange={() => { setVisibility('specific'); clearResult(); }} /><span>Specific friends</span></label>
      </div>
      {visibility === 'specific' && <div className="social-window-form__friend-list">
        {friendsLoading ? <p className="social-window-form__helper" role="status">Loading friends…</p>
          : friendsError ? <div className="social-window-form__friend-error" role="alert"><span>{friendsError}</span><button type="button" onClick={() => setFriendsRetry((attempt) => attempt + 1)}>Retry</button></div>
            : friends.length === 0 ? <p className="social-window-form__helper">No friends yet.</p>
              : friends.map((friend) => <label className="social-window-form__friend" key={friend.id}><input type="checkbox" value={friend.id} checked={selectedFriendIds.includes(friend.id)} onChange={() => toggleFriend(friend.id)} /><span>{friend.display_name}</span></label>)}
      </div>}
      {errors.visibility && <span className="social-window-form__error">{errors.visibility}</span>}
    </fieldset>

    {submitError && <div className="social-window-form__submit-error" role="alert"><span>{submitError}</span><button type="button" disabled={submitting} onClick={() => failedWindow && submitWindow(failedWindow)}>Retry</button></div>}
    {success && <p className="social-window-form__success" role="status">{success}</p>}
    <button className="primary-button social-window-form__submit" type="submit" disabled={!isValid || submitting}>{submitting ? 'Saving…' : 'Save availability'}</button>
  </form>;
}

export default SocialWindowForm;