/**
 * Notification service interface for desktop notifications.
 */
export interface INotificationService {
  /**
   * Show a desktop notification
   */
  notify(options: NotificationOptions): Promise<void>;

  /**
   * Check if notifications are supported
   */
  isSupported(): boolean;

  /**
   * Request notification permissions
   */
  requestPermission(): Promise<boolean>;
}

export interface NotificationOptions {
  /** Notification title */
  title: string;
  /** Notification body text */
  message: string;
  /** Notification icon */
  icon?: string;
  /** Sound to play */
  sound?: boolean;
  /** Timeout in milliseconds (0 = persistent) */
  timeout?: number;
  /** Actions/buttons */
  actions?: NotificationAction[];
  /** Callback when notification is clicked */
  onClick?: () => void;
}

export interface NotificationAction {
  label: string;
  callback: () => void;
}
