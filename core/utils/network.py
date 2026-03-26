def get_client_ip(request):
    """Определяет реальный IP пользователя даже за прокси."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Если несколько IP, берём первый (истинный клиент)
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
