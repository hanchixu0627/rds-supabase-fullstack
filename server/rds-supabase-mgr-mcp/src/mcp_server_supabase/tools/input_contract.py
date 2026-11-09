"""Reject extra arguments before SDK coercion or guardrail argument logging."""
import json
from huaweicloud_mcp_core.errors import McpToolError
from huaweicloud_mcp_core.guardrails.audit import AuditLogger
from huaweicloud_mcp_core.security import get_tool_risk
from mcp.types import CallToolResult, ListToolsResult, TextContent


class InputContractMiddleware:
    """Use registered tool schemas as the source of accepted top-level fields."""

    def __init__(self, server, audit_file=None):
        self.server = server
        self.audit = AuditLogger(file_path=audit_file)

    async def __call__(self, ctx, call_next):
        if ctx.method == 'tools/list':
            result = await call_next(ctx)
            if isinstance(result, ListToolsResult):
                for tool in result.tools:
                    tool.input_schema['additionalProperties'] = False
            elif isinstance(result, dict):
                for tool in result.get('tools', []):
                    tool['inputSchema']['additionalProperties'] = False
            return result
        if ctx.method != 'tools/call':
            return await call_next(ctx)
        params = ctx.params or {}
        name = params.get('name', '')
        arguments = params.get('arguments')
        tools = {tool.name: tool for tool in await self.server.list_tools()}
        tool = tools.get(name)
        if tool is None:
            return await call_next(ctx)
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict) or set(arguments) - set(tool.input_schema.get('properties', {})):
            error = McpToolError('MCP_INVALID_ARGS', 'Arguments do not match the supported tool fields',
                                 hint='Check tools/list. Resolve unsupported requirements before resubmitting; do not silently drop them.')
            # Neither unknown names nor values are safe to echo or audit.
            risk = get_tool_risk(name)
            self.audit.emit(tool=name, risk=risk.value if risk else 'UNDECLARED',
                            decision='blocked', error_code=error.code, params={})
            payload = error.to_dict()
            return CallToolResult(content=[TextContent(type='text', text=json.dumps(payload))],
                                  structured_content=payload, is_error=False)
        return await call_next(ctx)
