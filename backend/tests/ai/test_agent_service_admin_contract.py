from app.body_analysis.admin_config.schemas import AgentServiceCapabilitiesResponse


def test_capabilities_accept_runner_parameter_fields_from_agent_service() -> None:
    response = AgentServiceCapabilitiesResponse.model_validate(
        {
            "runners": [
                {
                    "agent": "antigravity",
                    "installed": True,
                    "version": "1.1.22",
                    "auth_state": "authenticated",
                    "auth_mode": "browser_link",
                    "models": [
                        {
                            "model_id": "gemini-test",
                            "supports_text_input": True,
                            "supports_image_input": True,
                            "supports_structured_output": True,
                            "supports_temperature": False,
                            "supports_max_output_tokens": False,
                        }
                    ],
                    "profiles": [
                        {
                            "profile_id": "antigravity-gemini-3.7-flash-high",
                            "agent": "antigravity",
                            "display_name": "Gemini 3.7 Flash (High)",
                            "model_id": "gemini-3.7-flash-high",
                            "effort": "high",
                            "task_kinds": ["workout_plan_generation", "body_photo_analysis"],
                            "fingerprint": "0123456789abcdef",
                            "supports_text_input": True,
                            "supports_image_input": True,
                            "supports_structured_output": True,
                        }
                    ],
                }
            ]
        }
    )

    assert response.runners[0].models[0].model_id == "gemini-test"
    assert response.runners[0].auth_mode == "browser_link"
    assert "supports_temperature" not in response.runners[0].models[0].model_dump()
    assert response.runners[0].profiles[0].profile_id == (
        "antigravity-gemini-3.7-flash-high"
    )
