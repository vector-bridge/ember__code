"""Skill executor — runs skills inline or forked."""

from typing import TYPE_CHECKING

from ember_code.utils.response import extract_response_text

if TYPE_CHECKING:
    from ember_code.config.settings import Settings
    from ember_code.pool import AgentPool
    from ember_code.skills.parser import SkillDefinition


class SkillExecutor:
    """Executes skills inline or in a forked sub-agent."""

    def __init__(self, pool: "AgentPool", settings: "Settings"):
        self.pool = pool
        self.settings = settings

    async def execute(self, skill: "SkillDefinition", arguments: str = "") -> str:
        """Execute a skill.

        Args:
            skill: The skill definition.
            arguments: Arguments passed to the skill.

        Returns:
            The execution result as text.
        """
        rendered = skill.render(arguments)

        if skill.context == "fork" and skill.agent:
            return await self._execute_forked(rendered, skill)
        return await self._execute_inline(rendered, skill)

    async def _execute_forked(self, prompt: str, skill: "SkillDefinition") -> str:
        """Execute a skill in a forked sub-agent."""
        agent_name = skill.agent or "editor"

        try:
            agent = self.pool.get(agent_name)
        except KeyError:
            return f"Error: Agent '{agent_name}' not found for skill '{skill.name}'."

        try:
            response = await agent.arun(prompt)
            return extract_response_text(response)
        except Exception as e:
            return f"Error executing skill '{skill.name}': {e}"

    async def _execute_inline(self, prompt: str, skill: "SkillDefinition") -> str:
        """Execute a skill inline using the editor agent."""
        try:
            agent = self.pool.get("editor")
        except KeyError:
            return f"Error: No 'editor' agent available for skill '{skill.name}'."

        try:
            response = await agent.arun(prompt)
            return extract_response_text(response)
        except Exception as e:
            return f"Error executing skill '{skill.name}': {e}"


# Backward compatibility
async def execute_skill(
    skill: "SkillDefinition",
    arguments: str,
    pool: "AgentPool",
    settings: "Settings",
) -> str:
    """Convenience wrapper around SkillExecutor.execute()."""
    executor = SkillExecutor(pool, settings)
    return await executor.execute(skill, arguments)
