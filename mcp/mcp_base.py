from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

@dataclass
class MCPRequest:
    """Represents a request made through the MCP."""
    request_id: str
    timestamp: datetime
    source: str
    action: str
    parameters: Dict[str, Any]
    context: Dict[str, Any]

@dataclass
class MCPResponse:
    """Represents a response from the MCP."""
    request_id: str
    timestamp: datetime
    status: str
    data: Any
    error: Optional[str] = None

class MCPComponent(ABC):
    """Base class for all MCP components."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"mcp.{name}")
    
    @abstractmethod
    def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle an incoming request."""
        pass

class MCPHost(MCPComponent):
    """The main environment that coordinates MCP interactions."""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.clients: List[MCPClient] = []
        self.servers: List[MCPServer] = []
    
    def register_client(self, client: 'MCPClient'):
        """Register a new MCP client."""
        self.clients.append(client)
        self.logger.info(f"Registered client: {client.name}")
    
    def register_server(self, server: 'MCPServer'):
        """Register a new MCP server."""
        self.servers.append(server)
        self.logger.info(f"Registered server: {server.name}")
    
    def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Route requests to appropriate servers."""
        # Log the request
        self.logger.info(f"Handling request {request.request_id} from {request.source}")
        
        # Find appropriate server
        for server in self.servers:
            if server.can_handle(request):
                return server.handle_request(request)
        
        return MCPResponse(
            request_id=request.request_id,
            timestamp=datetime.now(),
            status="error",
            data=None,
            error="No server available to handle request"
        )

class MCPClient(MCPComponent):
    """Component that interacts with MCP servers."""
    
    def __init__(self, name: str, host: MCPHost):
        super().__init__(name)
        self.host = host
        host.register_client(self)
    
    def make_request(self, action: str, parameters: Dict[str, Any], context: Dict[str, Any]) -> MCPResponse:
        """Make a request through the MCP."""
        request = MCPRequest(
            request_id=f"{self.name}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            source=self.name,
            action=action,
            parameters=parameters,
            context=context
        )
        return self.host.handle_request(request)
    
    def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle incoming requests (typically not used by clients)."""
        raise NotImplementedError("Clients typically don't handle incoming requests")

class MCPServer(MCPComponent):
    """Server that exposes specific tools or data."""
    
    def __init__(self, name: str, host: MCPHost, permissions: Dict[str, List[str]]):
        super().__init__(name)
        self.host = host
        self.permissions = permissions
        host.register_server(self)
    
    def can_handle(self, request: MCPRequest) -> bool:
        """Check if this server can handle the given request."""
        return request.action in self.permissions.get(request.source, [])
    
    def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle an incoming request."""
        if not self.can_handle(request):
            return MCPResponse(
                request_id=request.request_id,
                timestamp=datetime.now(),
                status="error",
                data=None,
                error="Permission denied"
            )
        
        try:
            # Process the request
            result = self._process_request(request)
            return MCPResponse(
                request_id=request.request_id,
                timestamp=datetime.now(),
                status="success",
                data=result
            )
        except Exception as e:
            self.logger.error(f"Error processing request: {str(e)}")
            return MCPResponse(
                request_id=request.request_id,
                timestamp=datetime.now(),
                status="error",
                data=None,
                error=str(e)
            )
    
    @abstractmethod
    def _process_request(self, request: MCPRequest) -> Any:
        """Process the actual request (to be implemented by specific servers)."""
        pass 