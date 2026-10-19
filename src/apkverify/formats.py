"""Pure tables about the ad library and AdMob (static-check-spec §1, §6; confirm.md A4, A6)."""

from __future__ import annotations

import re

# Remote Config keys the ad library reads (A4). Ad unit lists first, then the placement config.
AD_UNIT_LIST_KEYS: tuple[str, ...] = ("admob_id", "pangle_id", "gam_id")
ADS_CONFIG_KEY = "config_show_ads"
REQUIRED_KEYS: tuple[str, ...] = ("admob_id", ADS_CONFIG_KEY)  # absent/empty → RC-KEY-MISSING
ADMOB_LIST_KEY = "admob_id"  # the only list whose IDs must be AdMob-shaped
FALLBACK_KEYS: tuple[str, ...] = (*AD_UNIT_LIST_KEYS, ADS_CONFIG_KEY)  # assets/<key>.txt
FALLBACK_CHECKED_KEYS: tuple[str, ...] = ("admob_id", ADS_CONFIG_KEY)  # empty → APK-FALLBACK-EMPTY

ADMOB_APP_ID_META = "com.google.android.gms.ads.APPLICATION_ID"

ADMOB_UNIT_ID = re.compile(r"^ca-app-pub-(\d{16})/\d{10}$")
ADMOB_APP_ID = re.compile(r"^ca-app-pub-(\d{16})~\d{10}$")
GOOGLE_TEST_PUBLISHER = "3940256099942544"

# Spec "Định Dạng" → library adsType values that satisfy it (A6). Keys are casefolded.
FORMAT_TO_ADS_TYPES: dict[str, frozenset[str]] = {
    "native": frozenset({"native"}),
    "interstitial": frozenset({"interstitial"}),
    "open ad": frozenset({"open_app"}),
    "native full screen": frozenset({"native_full_screen", "native_interstitial"}),
    "banner adapt": frozenset({"banner_adaptive", "picture_in_picture"}),
}

# Library adsType → config_show_ads flag that turns the whole type off (static-check-spec §6.2).
DISABLE_ALL_FLAG = "disableAllConfig"
DISABLE_FLAG_BY_TYPE: dict[str, str] = {
    "open_app": "disableOpenApp",
    "interstitial": "disableInterstitial",
    "native": "disableNative",
    "native_full_screen": "disableNativeFullScreen",
    "native_interstitial": "disableNativeInterstitial",
    "banner": "disableBanner",
    "banner_adaptive": "disableBannerAdaptive",
    "banner_large": "disableBannerLarge",
    "banner_inline": "disableBannerInline",
    "banner_collapsible": "disableBannerCollapsible",
    "reward_video": "disableRewardVideo",
    "reward_inter": "disableRewardInter",
    "picture_in_picture": "disablePictureInPicture",
}


# Runtime log "source" (text before ":") → library adsType (runtime-check-spec §3). `show success` lines already carry
# the adsType itself ("native", "native_interstitial", ...), which maps to itself.
LOG_SOURCE_TO_ADS_TYPE: dict[str, str] = {
    "AdmobNativeAd": "native",
    "AdmobNativeFullScreenAd": "native_full_screen",
    "AdmobNativeInterstitialAd": "native_interstitial",
    "AdmobBannerAdaptiveAd": "banner_adaptive",
    "AdmobBannerCollapsibleAd": "banner_collapsible",
    "AdmobBanner300x250Ad": "banner",
    "AdmobOpenAppAd": "open_app",
    "AdmobPictureInPictureAd": "picture_in_picture",
    "AdmobRewardVideoAd": "reward_video",
    "AdmobRewardInterstitialAd": "reward_inter",
    "InterstitialAd": "interstitial",
    "Interstitial": "interstitial",
    "Interstitial Preload": "interstitial",
}


def log_source_ads_type(source: str) -> str:
    """adsType of a runtime log event; an unknown source is returned unchanged (it is usually an adsType already)."""
    return LOG_SOURCE_TO_ADS_TYPE.get(source, source)


def allowed_ads_types(spec_format: str) -> frozenset[str] | None:
    """Library adsType values allowed for a spec format; None when the format is not in the table."""
    return FORMAT_TO_ADS_TYPES.get(spec_format.strip().casefold())


def publisher(ad_id: str) -> str | None:
    """Publisher number of an AdMob unit ID or app ID, None if the string is neither."""
    match = ADMOB_UNIT_ID.match(ad_id) or ADMOB_APP_ID.match(ad_id)
    return match.group(1) if match else None


def is_google_test_id(ad_id: str) -> bool:
    return ad_id.startswith(f"ca-app-pub-{GOOGLE_TEST_PUBLISHER}")
