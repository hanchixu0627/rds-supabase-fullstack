"""Upstream tools-config whitelist ({"enabledTools": [...]}) support."""

import json
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer


async def apply_tools_config(config_path: str | None, server: MCPServer) -> None:
    """Filter registered tools against the upstream --tools-config semantics."""
    if not config_path:
        print(
            "No valid --tools-config specified or error loading config, "
            "enabling all available tools.",
            file=sys.stderr,
        )
        return
    enabled_tool_names: set[str] | None
    try:
        resolved_path = str(Path(config_path).resolve())
        print(f"Attempting to load tool configuration from: {resolved_path}", file=sys.stderr)
        if not Path(resolved_path).exists():
            raise RuntimeError(f"Tool configuration file not found at {resolved_path}")
        config_file_content = Path(resolved_path).read_text(encoding="utf-8")
        config_json: Any = json.loads(config_file_content)
        if not isinstance(config_json, dict) or not isinstance(
            config_json.get("enabledTools"), list
        ):
            raise RuntimeError(
                'Invalid config file format. Expected { "enabledTools": ["tool1", ...] }.'
            )
        tool_names: list[Any] = config_json["enabledTools"]
        if not all(isinstance(name, str) for name in tool_names):
            raise RuntimeError(
                'Invalid config file content. "enabledTools" must be an array of strings.'
            )
        ordered_names = [name.strip() for name in tool_names if name.strip()]
        enabled_tool_names = set(dict.fromkeys(ordered_names))
    except Exception as exc:
        print(
            f"Error loading or parsing tool config file '{config_path}': {exc}",
            file=sys.stderr,
        )
        print("Falling back to enabling all tools due to config error.", file=sys.stderr)
        enabled_tool_names = None
    if enabled_tool_names is None:
        print(
            "No valid --tools-config specified or error loading config, "
            "enabling all available tools.",
            file=sys.stderr,
        )
        return
    print(
        f"Whitelisting tools based on config: {', '.join(dict.fromkeys(ordered_names))}",
        file=sys.stderr,
    )
    available_tools = {tool.name: tool for tool in await server.list_tools()}
    for tool_name in available_tools:
        if tool_name not in enabled_tool_names:
            print(f"Tool {tool_name} disabled (not in config whitelist).", file=sys.stderr)
            server.remove_tool(tool_name)
    for requested_name in enabled_tool_names:
        if requested_name not in available_tools:
            print(
                f'Warning: Tool "{requested_name}" specified in config file not found.',
                file=sys.stderr,
            )
