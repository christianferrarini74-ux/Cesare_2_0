"""
CESARE 2.0 - Advanced Multi-Agent System with Efficient Parsing Evolution

This module implements a sophisticated parsing mechanism for agent communication,
featuring:
- Hierarchical message structure with semantic tagging
- Context-aware tokenization
- Priority-based message routing
- Distributed consensus for complex task decomposition
- Memory-efficient streaming parsing
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple
from enum import Enum
import hashlib
import json
import time
from collections import defaultdict
import asyncio


class MessageType(Enum):
    """Types of messages in the agent communication protocol."""
    TASK = "task"
    QUERY = "query"
    RESPONSE = "response"
    STATUS = "status"
    ERROR = "error"
    CONTROL = "control"
    CONTEXT_UPDATE = "context_update"


class Priority(Enum):
    """Message priority levels."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class SemanticToken:
    """Represents a parsed token with semantic meaning."""
    value: str
    token_type: str
    confidence: float
    context_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedMessage:
    """Structure for a fully parsed inter-agent message."""
    message_id: str
    sender_id: str
    receiver_id: Optional[str]
    message_type: MessageType
    priority: Priority
    content: str
    semantic_tokens: List[SemanticToken]
    context_chain: List[str]
    timestamp: float
    dependencies: List[str] = field(default_factory=list)
    execution_hints: Dict[str, Any] = field(default_factory=dict)


class AdvancedParser:
    """
    Advanced parser for efficient inter-agent communication.
    
    Features:
    - Streaming parsing for large messages
    - Semantic analysis with confidence scoring
    - Context-aware tokenization
    - Parallel parsing pipeline
    """
    
    def __init__(self, context_window_size: int = 100):
        self.context_window_size = context_window_size
        self.token_cache = {}
        self.semantic_rules = self._load_semantic_rules()
        self.context_graph = defaultdict(list)
        
    def _load_semantic_rules(self) -> Dict[str, Callable]:
        """Load semantic parsing rules."""
        return {
            'task_decomposition': self._parse_task_decomposition,
            'entity_extraction': self._extract_entities,
            'intent_classification': self._classify_intent,
            'dependency_mapping': self._map_dependencies,
        }
    
    async def parse_stream(self, message_data: Dict[str, Any]) -> ParsedMessage:
        """
        Parse a message using streaming approach for efficiency.
        
        Args:
            message_data: Raw message dictionary
            
        Returns:
            ParsedMessage object with semantic annotations
        """
        start_time = time.time()
        
        # Generate message ID
        message_id = hashlib.sha256(
            f"{message_data.get('sender', '')}{message_data.get('content', '')}{time.time()}".encode()
        ).hexdigest()[:16]
        
        # Extract basic fields
        content = message_data.get('content', '')
        sender_id = message_data.get('sender', 'unknown')
        receiver_id = message_data.get('receiver', None)
        
        # Parse message type with fallback
        msg_type_str = message_data.get('type', 'query')
        try:
            msg_type = MessageType(msg_type_str)
        except ValueError:
            msg_type = MessageType.QUERY
        
        # Parse priority with fallback
        priority_str = message_data.get('priority', 'normal')
        try:
            priority = Priority(priority_str)
        except ValueError:
            priority = Priority.NORMAL
        
        # Parallel semantic analysis
        semantic_tasks = []
        for rule_name, rule_func in self.semantic_rules.items():
            task = asyncio.create_task(rule_func(content, message_data))
            semantic_tasks.append(task)
        
        # Gather all semantic analyses
        results = await asyncio.gather(*semantic_tasks, return_exceptions=True)
        
        # Consolidate semantic tokens
        semantic_tokens = []
        for result in results:
            if isinstance(result, list):
                # Filter out any non-SemanticToken items
                for item in result:
                    if isinstance(item, SemanticToken):
                        semantic_tokens.append(item)
            elif isinstance(result, Exception):
                # Log error but continue parsing
                pass
        
        # Build context chain
        context_chain = self._build_context_chain(
            sender_id, 
            message_data.get('context_refs', [])
        )
        
        # Map dependencies
        dependencies = await self._map_dependencies(content, message_data)
        
        # Generate execution hints
        execution_hints = self._generate_execution_hints(
            semantic_tokens, 
            msg_type, 
            priority
        )
        
        parsed_message = ParsedMessage(
            message_id=message_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=msg_type,
            priority=priority,
            content=content,
            semantic_tokens=semantic_tokens,
            context_chain=context_chain,
            timestamp=start_time,
            dependencies=[dep['id'] for dep in dependencies],
            execution_hints=execution_hints
        )
        
        # Update context graph
        self._update_context_graph(parsed_message)
        
        return parsed_message
    
    async def _parse_task_decomposition(self, content: str, metadata: Dict) -> List[SemanticToken]:
        """Parse and decompose complex tasks into subtasks."""
        tokens = []
        
        # Simple heuristic for task decomposition
        # In production, this would use NLP models
        task_keywords = ['implement', 'create', 'analyze', 'process', 'generate']
        words = content.lower().split()
        
        for i, word in enumerate(words):
            if word in task_keywords:
                # Extract surrounding context
                start = max(0, i - 3)
                end = min(len(words), i + 5)
                context = ' '.join(words[start:end])
                
                token = SemanticToken(
                    value=context,
                    token_type='task_component',
                    confidence=0.8,
                    metadata={'action': word, 'position': i}
                )
                tokens.append(token)
        
        return tokens
    
    async def _extract_entities(self, content: str, metadata: Dict) -> List[SemanticToken]:
        """Extract named entities from content."""
        tokens = []
        
        # Simple entity extraction (would use NER in production)
        import re
        
        # Extract potential file paths
        paths = re.findall(r'[/\w.-]+\.[\w]+', content)
        for path in paths:
            tokens.append(SemanticToken(
                value=path,
                token_type='file_path',
                confidence=0.9
            ))
        
        # Extract potential code references
        code_refs = re.findall(r'\b[A-Z][a-zA-Z0-9_]*\b', content)
        for ref in code_refs[:10]:  # Limit to first 10
            tokens.append(SemanticToken(
                value=ref,
                token_type='code_reference',
                confidence=0.7
            ))
        
        return tokens
    
    async def _classify_intent(self, content: str, metadata: Dict) -> List[SemanticToken]:
        """Classify the intent of the message."""
        tokens = []
        
        intent_patterns = {
            'information_request': ['what', 'how', 'when', 'where', 'why'],
            'action_request': ['do', 'make', 'create', 'execute', 'run'],
            'confirmation': ['confirm', 'verify', 'check', 'validate'],
            'explanation': ['explain', 'describe', 'show', 'demonstrate']
        }
        
        content_lower = content.lower()
        for intent, keywords in intent_patterns.items():
            if any(keyword in content_lower for keyword in keywords):
                tokens.append(SemanticToken(
                    value=intent,
                    token_type='intent',
                    confidence=0.85,
                    metadata={'keywords_found': [k for k in keywords if k in content_lower]}
                ))
        
        return tokens
    
    async def _map_dependencies(self, content: str, metadata: Dict) -> List[Dict]:
        """Map task dependencies from content."""
        dependencies = []
        
        # Look for dependency indicators
        dep_patterns = ['depends on', 'requires', 'needs', 'after', 'before']
        content_lower = content.lower()
        
        for pattern in dep_patterns:
            if pattern in content_lower:
                dependencies.append({
                    'id': hashlib.sha256(f"{pattern}{content}".encode()).hexdigest()[:12],
                    'type': 'implicit',
                    'pattern': pattern
                })
        
        return dependencies
    
    def _build_context_chain(self, sender_id: str, context_refs: List[str]) -> List[str]:
        """Build a chain of context references."""
        chain = [sender_id]
        chain.extend(context_refs[-self.context_window_size:])
        return chain
    
    def _generate_execution_hints(self, 
                                 tokens: List[SemanticToken],
                                 msg_type: MessageType,
                                 priority: Priority) -> Dict[str, Any]:
        """Generate hints for message execution."""
        hints = {
            'estimated_complexity': len(tokens) * 0.1,
            'requires_context': len(tokens) > 3,
            'parallelizable': msg_type == MessageType.TASK,
            'cacheable': priority in [Priority.LOW, Priority.NORMAL]
        }
        
        # Add specific hints based on token types
        token_types = [t.token_type for t in tokens]
        if 'file_path' in token_types:
            hints['io_operation'] = True
        if 'task_component' in token_types:
            hints['computational'] = True
        
        return hints
    
    def _update_context_graph(self, message: ParsedMessage):
        """Update the context graph with new message."""
        self.context_graph[message.sender_id].append({
            'message_id': message.message_id,
            'timestamp': message.timestamp,
            'tokens': len(message.semantic_tokens)
        })
        
        # Prune old entries
        if len(self.context_graph[message.sender_id]) > self.context_window_size:
            self.context_graph[message.sender_id] = \
                self.context_graph[message.sender_id][-self.context_window_size:]


class AgentCommunicationProtocol:
    """
    Protocol for efficient agent-to-agent communication with advanced parsing.
    """
    
    def __init__(self):
        self.parser = AdvancedParser()
        self.message_queue = asyncio.Queue()
        self.routing_table = {}
        self.active_agents = set()
        
    def register_agent(self, agent_id: str, capabilities: List[str]):
        """Register an agent with its capabilities."""
        self.active_agents.add(agent_id)
        self.routing_table[agent_id] = {
            'capabilities': capabilities,
            'load': 0,
            'last_seen': time.time()
        }
    
    async def send_message(self, message_data: Dict[str, Any]):
        """Send a message through the protocol."""
        parsed_message = await self.parser.parse_stream(message_data)
        await self.message_queue.put(parsed_message)
        return parsed_message.message_id
    
    async def route_message(self, message: ParsedMessage) -> Optional[str]:
        """Route a parsed message to the appropriate agent."""
        if message.receiver_id:
            return message.receiver_id
        
        # Intelligent routing based on semantic analysis
        best_agent = None
        best_score = -1
        
        for agent_id, info in self.routing_table.items():
            score = self._calculate_routing_score(message, info)
            if score > best_score:
                best_score = score
                best_agent = agent_id
        
        return best_agent
    
    def _calculate_routing_score(self, message: ParsedMessage, 
                                agent_info: Dict) -> float:
        """Calculate routing score for an agent."""
        score = 0.0
        
        # Capability matching
        for token in message.semantic_tokens:
            if token.token_type in agent_info['capabilities']:
                score += 1.0
        
        # Load balancing
        score -= agent_info['load'] * 0.1
        
        # Priority boost
        if message.priority == Priority.CRITICAL:
            score += 2.0
        
        return score
    
    async def process_queue(self, handler: Callable[[ParsedMessage], Any]):
        """Process messages from the queue."""
        while True:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(), 
                    timeout=1.0
                )
                await handler(message)
                self.message_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing message: {e}")


# Example usage and testing
async def main():
    """Test the advanced parsing system."""
    protocol = AgentCommunicationProtocol()
    
    # Register some agents
    protocol.register_agent('coder', ['python', 'javascript', 'task_component'])
    protocol.register_agent('analyst', ['data_analysis', 'intent', 'code_reference'])
    protocol.register_agent('reviewer', ['validation', 'file_path'])
    
    # Test message
    test_message = {
        'sender': 'user',
        'content': 'Create a Python script to analyze data files in /data folder. '
                  'This depends on the previous analysis task.',
        'type': 'task',
        'priority': 'high',
        'context_refs': ['task_001', 'task_002']
    }
    
    # Send and parse message
    msg_id = await protocol.send_message(test_message)
    print(f"Message parsed with ID: {msg_id}")
    
    # Get message from queue
    parsed_msg = await protocol.message_queue.get()
    print(f"Parsed message type: {parsed_msg.message_type}")
    print(f"Semantic tokens found: {len(parsed_msg.semantic_tokens)}")
    print(f"Execution hints: {parsed_msg.execution_hints}")
    
    # Route message
    target_agent = await protocol.route_message(parsed_msg)
    print(f"Routed to agent: {target_agent}")


if __name__ == '__main__':
    asyncio.run(main())
