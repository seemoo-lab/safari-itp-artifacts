from dataclasses import dataclass
from typing import Dict


@dataclass
class DeviceConfig:
    name: str
    user_agent: str
    viewport: Dict[str, int]
    is_mobile: bool

    locale: str
    timezone_id: str

    device_scale_factor: int = None # only if is_mobile is True


DEVICES = {

    "safari_desktop": DeviceConfig(
        name="Safari Desktop",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15",
        viewport={"width": 1920, "height": 1080},
        is_mobile=False,
        locale="en-US",
        timezone_id="Europe/Berlin"
    ),

    "iphone_16": DeviceConfig(
        name="iPhone 16",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Mobile/15E148 Safari/604.1",
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        locale="en-US",
        timezone_id="Europe/Berlin",
        device_scale_factor=2
    )
}

