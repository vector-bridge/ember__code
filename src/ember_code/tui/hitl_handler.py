"""HITLHandler — handles Human-in-the-Loop requirements."""

from typing import TYPE_CHECKING, Any

from ember_code.config.tool_permissions import FUNC_TO_TOOL, ToolPermissions
from ember_code.tui.widgets import PermissionDialog
from ember_code.tui.widgets._messages import TOOL_FRIENDLY_NAMES

if TYPE_CHECKING:
    from ember_code.tui.app import EmberApp
    from ember_code.tui.conversation_view import ConversationView


class HITLHandler:
    """Handles Human-in-the-Loop requirements: confirmations and user input.

    Integrates with ToolPermissions to check argument-specific rules
    and persist user decisions.
    """

    def __init__(
        self,
        app: "EmberApp",
        conversation: "ConversationView",
        permissions: ToolPermissions | None = None,
    ):
        self._app = app
        self._conversation = conversation
        self._permissions = permissions or ToolPermissions()
        # Session-level one-time approvals: set of "ToolName(args_str)"
        self._session_approvals: set[str] = set()

    async def handle(self, executor: Any, run_response: Any) -> None:
        """Resolve all active requirements on a paused run.

        Does NOT call ``acontinue_run`` — the caller is responsible for
        continuing the run (e.g. with streaming) after requirements are resolved.
        """
        for requirement in run_response.active_requirements:
            if requirement.needs_confirmation:
                await self._handle_confirmation(requirement)
            elif requirement.needs_user_input:
                self._handle_user_input(requirement)

    async def _handle_confirmation(self, requirement: Any) -> None:
        tool_exec = requirement.tool_execution
        if not tool_exec:
            requirement.confirm()
            return

        func_name = tool_exec.tool_name or ""
        tool_args = tool_exec.tool_args or {}
        tool_name = FUNC_TO_TOOL.get(func_name, func_name)
        friendly = TOOL_FRIENDLY_NAMES.get(func_name, tool_name)

        # Check argument-specific rules — might already be allowed
        level = self._permissions.check(tool_name, func_name, tool_args)
        if level == "allow":
            requirement.confirm()
            return
        if level == "deny":
            requirement.reject("Denied by permission rules")
            return

        # Check session-level approvals
        args_str = _format_args_short(tool_args)
        session_key = f"{tool_name}({args_str})"
        if session_key in self._session_approvals:
            requirement.confirm()
            return

        # Show the permission dialog
        details = _format_args_detail(tool_args)
        dialog = PermissionDialog(
            tool_name=friendly,
            details=details,
        )
        await self._app.mount(dialog)
        dialog.focus()

        approved = await dialog.wait_for_decision()
        if not approved:
            requirement.reject("User denied via TUI")
            return

        # Handle the approval choice
        choice = dialog.last_choice
        requirement.confirm()

        if choice == "once":
            self._session_approvals.add(session_key)
        elif choice == "always":
            # Save the specific rule
            rule = _build_rule(tool_name, tool_args)
            self._permissions.save_rule(rule, "allow")
            self._conversation.append_info(f"Saved rule: allow {rule}")
        elif choice == "similar":
            # Save a pattern rule
            rule = _build_pattern_rule(tool_name, tool_args)
            self._permissions.save_rule(rule, "allow")
            self._conversation.append_info(f"Saved rule: allow {rule}")

    def _handle_user_input(self, requirement: Any) -> None:
        self._conversation.append_info("Agent is requesting additional input.")
        requirement.provide_user_input({})


def _format_args_short(args: dict) -> str:
    """Short args representation for session key."""
    if "args" in args and isinstance(args["args"], list):
        return " ".join(str(a) for a in args["args"])
    for key in ("path", "file_path", "url", "query"):
        if key in args:
            return str(args[key])
    return str(args)[:100]


def _format_args_detail(args: dict) -> str:
    """Full args for the permission dialog display.

    Shell commands: ``$ git status``
    File ops: ``path: src/ember_code/tui/app.py``
    """
    # Shell commands — show as a command line
    if "args" in args and isinstance(args["args"], list):
        cmd = " ".join(str(a) for a in args["args"])
        return f"$ {cmd}"
    # File operations — show the full path
    for key in ("path", "file_path", "file_name"):
        if key in args:
            return str(args[key])
    # Everything else — show all args untruncated
    parts = []
    for k, v in args.items():
        parts.append(f"{k}: {v}")
    return "\n".join(parts)


def _build_rule(tool_name: str, tool_args: dict) -> str:
    """Build a specific rule string from a tool call.

    e.g. Bash(git status), Edit(src/ember_code/tui/app.py)
    """
    args_str = _format_args_short(tool_args)
    if args_str:
        return f"{tool_name}({args_str})"
    return tool_name


def _build_pattern_rule(tool_name: str, tool_args: dict) -> str:
    """Build a pattern rule from a tool call.

    e.g. Bash(git:*), Edit(path:src/ember_code/*)
    """
    if "args" in tool_args and isinstance(tool_args["args"], list):
        cmd = tool_args["args"]
        if cmd:
            return f"{tool_name}({cmd[0]}:*)"
    for key in ("path", "file_path"):
        if key in tool_args:
            from pathlib import Path

            parent = str(Path(str(tool_args[key])).parent)
            if parent and parent != ".":
                return f"{tool_name}(path:{parent}/*)"
    if "url" in tool_args:
        from urllib.parse import urlparse

        domain = urlparse(str(tool_args["url"])).netloc
        if domain:
            return f"{tool_name}(domain:{domain})"
    return tool_name
