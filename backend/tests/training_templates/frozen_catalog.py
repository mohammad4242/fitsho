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
    "p08-3-day-upper-lower-upper-beginner": "06fe3806fa2b85c0fde33e7fb2a0f22c22deb7c4ae5e025aabd67380ed9e9f7a",
    "p09-3-day-upper-lower-upper-intermediate": "3da6e0f9238ac83fe45f756068a0c76cceab614d0db573bbf83747812eea82b6",
    "p10-3-day-upper-lower-upper-advanced": "f25d87380ef0ed615c28d0ee1ff0ede38e6dcef5e8510b5c9ed44dd8db97d94b",
    "p11-3-day-lower-upper-lower-beginner": "f0e4ce5e98985ba9d6f6cd55d43a8bfccf46f4b4a2725fedb0d09d1328c3efbb",
    "p12-3-day-lower-upper-lower-intermediate": "7bd0980749843cd048b1e230e910f2f41e7773dee9dc7013018064a057bbf011",
    "p13-3-day-lower-upper-lower-advanced": "2a43a4cf2839e259000fa5ecd83d37707cbc492f36d89aa5e1524936e76265f9",
    "p14-4-day-upper-lower-upper-lower-first-month": "9d06e467f8146491873a2b3f05595fc65ffc24354e64cf53cec090d166488dd9",
    "p15-4-day-upper-lower-upper-lower-beginner": "4e6d3f848d7cccc981d1725e99335bb0c295e60271e6c1ce50ee0ea4f6456bec",
    "p16-4-day-upper-lower-upper-lower-intermediate": "a99b7aaa4b18290754e11d8269d5bf55f981ce5499e4ba86bcd9e2b60f3e3663",
    "p17-4-day-upper-lower-upper-lower-advanced": "ea3f08d13ebfdf769e37738f135dc28806e09fea6f5385b1a25aec50be68d681",
    "p18-4-day-3-upper-1-lower-beginner": "ec4fdc4d8bb48051caa68984540094b299506eb6f5e1e63853f21d0fbc952ea2",
    "p19-4-day-3-upper-1-lower-intermediate": "d572cc608fa7934e7622f39a3fac1ff78a79e660ad86a57431f40f1dc91365cc",
    "p20-4-day-3-upper-1-lower-advanced": "4c6b8c3442484f789ad88950e994b4c7439be6c14ca9587f02481b4846641b7c",
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
