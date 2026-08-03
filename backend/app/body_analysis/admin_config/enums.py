from enum import StrEnum


class AITaskType(StrEnum):
    WORKOUT_PLAN_GENERATION = "workout_plan_generation"
    BODY_PHOTO_ANALYSIS = "body_photo_analysis"
    PROGRESS_COMPARISON = "progress_comparison"
    SPECIALIST_SUMMARY = "specialist_summary"


class AIProviderName(StrEnum):
    OPENROUTER = "openrouter"


class AIRoutingPolicy(StrEnum):
    DENY_PROVIDER_DATA_COLLECTION = "deny_provider_data_collection"
    ZERO_DATA_RETENTION = "zero_data_retention"
    REQUIRE_SUPPORTED_PARAMETERS = "require_supported_parameters"


class AIAuditAction(StrEnum):
    CONFIG_UPDATED = "config_updated"
    CREDENTIAL_REPLACED = "credential_replaced"
    CONNECTION_TESTED = "connection_tested"
    MODEL_CATALOG_REFRESHED = "model_catalog_refreshed"
