"""اعتبارسنجی مستقل از دیتابیس برای IP، Subnet و ظرفیت عددی.

خطای قالب نامعتبر مانع ذخیره است؛ موارد قابل‌بررسی مانند Gateway خارج شبکه هشدارند.
Subnet خالی از روی IP حدس زده نمی‌شود و برچسب OS به‌صورت پنهان بازنویسی نمی‌شود.
"""

import ipaddress
from decimal import Decimal, InvalidOperation
from rest_framework.exceptions import ValidationError


def subnet(value, ipv6=False):
    s = str(value if value is not None else "").strip()
    if not s:
        return ""
    try:
        if "." in s:
            if ipv6:
                raise ValueError()
            prefix = ipaddress.IPv4Network("0.0.0.0/" + s).prefixlen
        else:
            prefix = int(s.lstrip("/"))
            if not 0 <= prefix <= (128 if ipv6 else 32):
                raise ValueError()
        return "/" + str(prefix)
    except ValueError:
        raise ValidationError({"subnet": "ماسک یا پیشوند نامعتبر است"})


def capacity(value, integer=False):
    try:
        x = Decimal(str(value if value not in (None, "") else 0))
        if not x.is_finite() or x < 0 or x > Decimal("9999999999.99"):
            raise ValueError()
        if integer and (x != x.to_integral_value() or x > 1000000):
            raise ValueError()
        if x.as_tuple().exponent < -2:
            raise ValueError()
        return int(x) if integer else str(x.quantize(Decimal(".01")))
    except (ValueError, InvalidOperation):
        raise ValidationError("ظرفیت نامعتبر است؛ فقط عدد غیرمنفی پذیرفته می‌شود")


def network_fields(data):
    warnings = []
    parsed = {}
    if data.get('ip') and '/' in str(data['ip']):
        try:
            interface = ipaddress.ip_interface(str(data['ip']).strip())
            prefix = '/' + str(interface.network.prefixlen)
            if data.get('subnet') and subnet(data['subnet'], interface.version == 6) != prefix:
                raise ValidationError({'subnet': 'ساب‌نت ستون جدا با مقدار IP یکسان نیست'})
            data['ip'] = str(interface.ip)
            data['subnet'] = prefix
        except ValueError:
            raise ValidationError({'ip': 'آدرس IP یا پیشوند نامعتبر است'})
    for key in ["ip", "gateway"]:
        if str(data.get(key) or '').strip() == '0':
            data[key] = ''
        try:
            parsed[key] = ipaddress.ip_address(data[key]) if data.get(key) else None
        except ValueError:
            raise ValidationError({key: "آدرس IP نامعتبر است"})
        data[key] = str(parsed[key]) if parsed[key] else ""
    data["subnet"] = subnet(
        data.get("subnet"), bool(parsed["ip"] and parsed["ip"].version == 6)
    )
    if parsed["ip"] and parsed["gateway"]:
        if parsed["ip"].version != parsed["gateway"].version:
            raise ValidationError({"gateway": "نسخه IP و Gateway یکسان نیست"})
        if data["subnet"] and parsed["gateway"] not in ipaddress.ip_network(
            data["ip"] + data["subnet"], strict=False
        ):
            warnings.append("Gateway خارج از Subnet است")
    if parsed["ip"] and data["subnet"]:
        net = ipaddress.ip_network(data["ip"] + data["subnet"], strict=False)
        if (
            parsed["ip"].version == 4
            and net.prefixlen < 31
            and parsed["ip"] in [net.network_address, net.broadcast_address]
        ):
            warnings.append("IP آدرس شبکه یا Broadcast است")
    return warnings


def normalize_interfaces(values):
    if not isinstance(values, list) or len(values) > 64:
        raise ValidationError({'interfaces': 'حداکثر ۶۴ آدرس شبکه مجاز است'})
    result, warnings, seen = [], [], set()
    for raw in values:
        if not isinstance(raw, dict) or set(raw) - {'ip', 'subnet', 'gateway', 'network'}:
            raise ValidationError({'interfaces': 'مشخصات شبکه نامعتبر است'})
        item = {key: str(raw.get(key) or '').strip() for key in ['ip', 'subnet', 'gateway', 'network']}
        if not any(item.values()):
            continue
        if len(item['network']) > 180:
            raise ValidationError({'network': 'نام شبکه بیش از حد طولانی است'})
        warnings.extend(network_fields(item))
        context = (item['network'], item['ip'])
        if item['ip'] and context in seen:
            raise ValidationError({'interfaces': 'آدرس IP در همان شبکه برای این سرور تکرار شده است'})
        seen.add(context)
        result.append(item)
    return result, warnings
