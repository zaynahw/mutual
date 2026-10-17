import type { ComponentType } from 'react';
import type { CreatedSocialWindow } from '../api.js';

declare const SocialWindowForm: ComponentType<{
  userId: string;
  timeZone?: string;
  onCreated?: (window: CreatedSocialWindow) => void;
}>;

export default SocialWindowForm;