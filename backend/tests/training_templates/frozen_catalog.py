from __future__ import annotations

# Hash literals intentionally stay readable as one value per snapshot row.
# ruff: noqa: E501
import dataclasses
import hashlib
import json
from enum import StrEnum

FROZEN_2_3_4_SIGNATURES = {
    "p01-2-day-full-body-ab-first-month": "004f9561f4c7bc80309cfaa5f629b9e1bd9b74b5a1300adc88d854fde1207134",
    "p02-2-day-full-body-ab-beginner": "8988c14a82be6f2b58dc74095ac793f5ec456a5f5d86ff4ee9bcd3de8dddb6fa",
    "p03-2-day-full-body-ab-intermediate": "d7532f25ffa69dd8e7c7279f73947111532d04ace727b51a2f52bd7461317d11",
    "p04-3-day-upper-lower-full-first-month": "2cea8f11d21e1578dcb159396a3c40530bbb5eb60bbcf81d27949fc4e8ed1f58",
    "p05-3-day-upper-lower-full-beginner": "247e542e681f72117876d8a50177e4fe1a43b831489cb6f8eaa72024fb2f98c8",
    "p06-3-day-upper-lower-full-intermediate": "5d8559c868fd838c4f2763d4afbfa8dcbab8fc8b6ac00f82b1f065f7024ead14",
    "p07-3-day-upper-lower-full-advanced": "1a95df4fc481dd6be3e576588f9682650f2fb4c4b772623d48a260cc7f4c58dc",
    "p08-3-day-upper-lower-upper-beginner": "aa542ba03e9216b003b74054a31711c3b92e2ffa4fa381df134ed61879434377",
    "p09-3-day-upper-lower-upper-intermediate": "6c3eb680e0293bc878b457cad3756fa330cedc232c9c882359e6cab5f0f1e317",
    "p10-3-day-upper-lower-upper-advanced": "e6a07c9de34fe885c1d1587a090e740bed25c693a42077f1f939cf546afb56a8",
    "p11-3-day-lower-upper-lower-beginner": "f0e4ce5e98985ba9d6f6cd55d43a8bfccf46f4b4a2725fedb0d09d1328c3efbb",
    "p12-3-day-lower-upper-lower-intermediate": "7bd0980749843cd048b1e230e910f2f41e7773dee9dc7013018064a057bbf011",
    "p13-3-day-lower-upper-lower-advanced": "2a43a4cf2839e259000fa5ecd83d37707cbc492f36d89aa5e1524936e76265f9",
    "p14-4-day-upper-lower-upper-lower-first-month": "9d06e467f8146491873a2b3f05595fc65ffc24354e64cf53cec090d166488dd9",
    "p15-4-day-upper-lower-upper-lower-beginner": "4e6d3f848d7cccc981d1725e99335bb0c295e60271e6c1ce50ee0ea4f6456bec",
    "p16-4-day-upper-lower-upper-lower-intermediate": "a99b7aaa4b18290754e11d8269d5bf55f981ce5499e4ba86bcd9e2b60f3e3663",
    "p17-4-day-upper-lower-upper-lower-advanced": "ea3f08d13ebfdf769e37738f135dc28806e09fea6f5385b1a25aec50be68d681",
    "p18-4-day-3-upper-1-lower-beginner": "9bf6894261a0225317021e59bf520a5557444b7d4c313dec0c8c020ee403efe5",
    "p19-4-day-3-upper-1-lower-intermediate": "df59bd3e94c95ec1613a133245d4135f6b3816faffc5698e83032a5560172e84",
    "p20-4-day-3-upper-1-lower-advanced": "4e81dec4ee027713e554d6900f97150b0ecb3444c308d8dd198c8d6d9ac41a85",
    "p21-4-day-3-lower-1-upper-beginner": "54f84ba7c1bfb50a1f81a7e159364c0c643fc3274b9fe50ad65aaa66e2577bdc",
    "p22-4-day-3-lower-1-upper-intermediate": "863bc6a14e3b31f2ee5a6145d3e2aedf4c04e0ae5e815ed9607d09f2e7741ca4",
    "p23-4-day-3-lower-1-upper-advanced": "d7335bfc742c55314030c78c355d1d4f1b699602d600ca104756ba2d06337291",
    "p24-4-day-push-pull-quads-posterior-intermediate": "4675d97134d4920456c4272cc2fa86e8fc5b3207c17f70d9556500cc410832a4",
    "p25-4-day-push-pull-quads-posterior-advanced": "8d55754679e5d720792ddf5027866a6fc33624138e7ce93bb818acaf6b88efe7",
}


def seed_signature(seed: object) -> str:
    def normalize(value: object) -> object:
        if isinstance(value, StrEnum):
            return value.value
        if dataclasses.is_dataclass(value):
            return {
                field.name: normalize(getattr(value, field.name))
                for field in dataclasses.fields(value)
            }
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [normalize(item) for item in value]
        return value

    payload = json.dumps(normalize(seed), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()
