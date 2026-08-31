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
                }
            ]
        }
    )

    assert response.runners[0].models[0].model_id == "gemini-test"
    assert response.runners[0].auth_mode == "browser_link"
    assert "supports_temperature" not in response.runners[0].models[0].model_dump()
