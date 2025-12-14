import ipaddress
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_ip_allowed(client_ip: str) -> bool:
    """
    Проверяет, разрешен ли IP-адрес.

    Args:
        client_ip: IP-адрес клиента

    Returns:
        bool: True если IP разрешен, иначе False
    """
    if not settings.IP_WHITELIST:
        return False

    try:
        ip = ipaddress.ip_address(client_ip)

        # Проверяем каждый паттерн из whitelist
        for allowed_pattern in settings.IP_WHITELIST:
            # Если это CIDR-нотация
            if "/" in allowed_pattern:
                network = ipaddress.ip_network(allowed_pattern, strict=False)
                if ip in network:
                    return True
            # Если это конкретный IP
            else:
                allowed_ip = ipaddress.ip_address(allowed_pattern)
                if ip == allowed_ip:
                    return True

        return False

    except ValueError as e:
        logger.warning(f"Invalid IP address {client_ip}: {e}")
        return False
