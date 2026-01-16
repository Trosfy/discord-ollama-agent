import React, { useEffect } from "react";
import { Box, Text } from "ink";
import { useAppState, useDispatch } from "../../context/StateProvider";

export function NotificationList() {
  const state = useAppState();
  const dispatch = useDispatch();
  const { colors } = state.ui.theme;

  const notifications = state.ui.notifications;

  // Auto-dismiss notifications
  useEffect(() => {
    notifications.forEach((notification) => {
      if (notification.autoDismiss && notification.duration) {
        const timer = setTimeout(() => {
          dispatch({
            type: "NOTIFICATION_DISMISSED",
            id: notification.id,
          });
        }, notification.duration);

        return () => clearTimeout(timer);
      }
    });
  }, [notifications, dispatch]);

  if (notifications.length === 0) {
    return null;
  }

  return (
    <Box
      position="absolute"
      flexDirection="column"
      gap={1}
      marginTop={2}
      marginRight={2}
    >
      {notifications.slice(0, 5).map((notification) => (
        <NotificationItem
          key={notification.id}
          notification={notification}
          colors={colors}
        />
      ))}
    </Box>
  );
}

interface NotificationItemProps {
  notification: {
    id: string;
    type: "info" | "success" | "warning" | "error";
    title: string;
    message?: string;
  };
  colors: Record<string, string>;
}

function NotificationItem({ notification, colors }: NotificationItemProps) {
  const getTypeStyle = () => {
    switch (notification.type) {
      case "success":
        return { icon: "✓", color: colors.success };
      case "warning":
        return { icon: "⚠", color: colors.warning };
      case "error":
        return { icon: "✗", color: colors.error };
      default:
        return { icon: "ℹ", color: colors.info };
    }
  };

  const style = getTypeStyle();

  return (
    <Box
      borderStyle="round"
      borderColor={style.color}
      paddingX={1}
      flexDirection="column"
    >
      <Box gap={1}>
        <Text color={style.color}>{style.icon}</Text>
        <Text color={colors.text} bold>
          {notification.title}
        </Text>
      </Box>
      {notification.message && (
        <Box paddingLeft={2}>
          <Text color={colors.textMuted}>{notification.message}</Text>
        </Box>
      )}
    </Box>
  );
}
