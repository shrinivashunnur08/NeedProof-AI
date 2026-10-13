
from typing import Literal

from pydantic import BaseModel, Field


class PowerProfile(BaseModel):
    voltage_v: int = Field(ge=5, le=48)
    current_ma: int = Field(ge=100, le=5000)


class CompatibilityInput(BaseModel):
    device_model: str = Field(
        min_length=2, max_length=120
    )

    device_supports_usb_pd: bool | None = None

    device_required_power_w: int = Field(
        ge=1, le=240
    )

    device_required_voltage_v: int = Field(
        ge=5, le=48
    )

    charger_supports_usb_pd: bool | None = None

    charger_profiles: list[PowerProfile] = Field(
        default_factory=list,
        max_length=12,
    )

    cable_current_rating_a: Literal[3, 5] | None = None


def evaluate_compatibility(
    data: CompatibilityInput,
) -> dict:
    """
    Compare user/operator-entered specifications only.

    Does not authenticate the product, the merchant,
    or the accuracy of the supplied specifications.
    """

    def outcome(
        status: str,
        reasons: list[str],
        next_action: str,
    ) -> dict:
        return {
            "status": status,
            "device_model": data.device_model,
            "reasons": reasons,
            "recommended_next_action": next_action,
            "product_authenticity_verified": False,
            "specification_source_verified": False,
            "purchase_allowed": False,
            "notice": (
                "Result is based on entered specifications. "
                "It does not prove actual device compatibility, "
                "product authenticity or purchase readiness."
            ),
        }

    if (
        data.device_supports_usb_pd is False
        or data.charger_supports_usb_pd is False
    ):
        return outcome(
            "REPORTED_SPEC_MISMATCH",
            ["USB-C PD support is reported as absent."],
            "Find a product compatible with the device.",
        )

    if (
        data.device_supports_usb_pd is None
        or data.charger_supports_usb_pd is None
    ):
        return outcome(
            "INSUFFICIENT_SPEC_INPUT",
            ["USB-C PD support is not established."],
            "Confirm USB-C PD support for both devices.",
        )

    if not data.charger_profiles:
        return outcome(
            "INSUFFICIENT_SPEC_INPUT",
            ["No charger output profiles were provided."],
            "Obtain the charger's published PD output profiles.",
        )

    matching = [
        profile
        for profile in data.charger_profiles
        if (
            profile.voltage_v
            == data.device_required_voltage_v
        )
    ]

    if not matching:
        return outcome(
            "REPORTED_SPEC_MISMATCH",
            [
                "No declared output profile matches "
                "the required voltage."
            ],
            "Find a charger with the required voltage profile.",
        )

    required_current_ma = (
        data.device_required_power_w * 1000
        + data.device_required_voltage_v - 1
    ) // data.device_required_voltage_v

    max_current_ma = max(
        profile.current_ma for profile in matching
    )

    if max_current_ma < required_current_ma:
        available_w = (
            data.device_required_voltage_v
            * max_current_ma
        ) / 1000

        return outcome(
            "REPORTED_SPEC_MISMATCH",
            [
                f"Matching voltage profile supplies at most "
                f"{available_w:g} W, below the stated "
                f"{data.device_required_power_w} W requirement."
            ],
            "Select a charger with sufficient rated output.",
        )

    if required_current_ma > 3000:
        if data.cable_current_rating_a is None:
            return outcome(
                "INSUFFICIENT_SPEC_INPUT",
                [
                    "The requested power needs more than 3 A "
                    "at the stated voltage.",
                    "The USB-C cable's 5 A capability "
                    "has not been established.",
                ],
                "Confirm a suitable 5 A-rated cable.",
            )

        if data.cable_current_rating_a == 3:
            return outcome(
                "REPORTED_SPEC_MISMATCH",
                [
                    "The stated 3 A cable rating is "
                    "insufficient for the required current."
                ],
                "Use an appropriately rated cable.",
            )

    return outcome(
        "CONDITIONAL_SPEC_MATCH",
        [
            "The entered charger output profile meets "
            "the entered voltage and power requirements.",
            "The actual product, device charging behavior "
            "and evidence provenance remain unverified.",
        ],
        "Verify source specifications and merchant evidence.",
    )
