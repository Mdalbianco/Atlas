from app.services.notification_service import NotificationService


service = NotificationService()

result = service.send_sync(
    "✅ Test Atlas\n\nLe notifiche Telegram funzionano."
)

print("Messaggio inviato:", result)