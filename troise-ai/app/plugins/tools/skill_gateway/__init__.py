"""Skill Gateway Tool - Access skill instructions on demand."""

from .tool import SkillGatewayTool, create_skill_gateway_tool

PLUGIN = {
    "name": "skill_gateway",
    "type": "tool",
    "description": "Access skill instructions and capabilities on demand",
    "factory": create_skill_gateway_tool,
}

__all__ = ["SkillGatewayTool", "create_skill_gateway_tool", "PLUGIN"]
