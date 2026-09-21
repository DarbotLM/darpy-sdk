from darpy_sdk.server.apps import Apps
from darpy_sdk.server.mcpserver import MCPServer

mcp = MCPServer("demo", extensions=[Apps()])
