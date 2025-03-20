from typing import List, Dict, Any, Optional, Union

class MCPAction:
    """Action to be processed by an MCP server"""
    
    def __init__(self, name: str, parameters: Dict[str, Any] = None):
        self.name = name
        self.parameters = parameters or {}


class MCPContext:
    """Context containing actions to be processed"""
    
    def __init__(self, actions: List[MCPAction] = None):
        self.actions = actions or []


class MCPResponse:
    """Response from an MCP server"""
    
    def __init__(self, content: str):
        self.content = content


class MCPStreamingResponse:
    """Streaming response from an MCP server"""
    
    def __init__(self, content_stream):
        self.content_stream = content_stream


class MCPModelID:
    """Identifier for an MCP model"""
    
    def __init__(self, name: str, version: Optional[str] = None):
        self.name = name
        self.version = version


class MCPModel:
    """Base class for MCP models"""
    
    def get_model_id(self) -> MCPModelID:
        return MCPModelID(name=self.__class__.__name__)


class MCPServer:
    """Base class for MCP servers"""
    
    async def process(self, context: MCPContext) -> Union[MCPResponse, MCPStreamingResponse]:
        """Process the context and return a response"""
        raise NotImplementedError("Subclasses must implement this method")
