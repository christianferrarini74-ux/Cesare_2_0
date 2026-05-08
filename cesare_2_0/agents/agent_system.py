"""
CESARE 2.0 - Agent Base Class and Specialized Agents

This module defines the base agent class and specialized agent implementations
that work with the advanced parsing system.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import asyncio
import time
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parsing_engine import ParsedMessage, MessageType, Priority, SemanticToken


@dataclass
class AgentState:
    """Represents the current state of an agent."""
    status: str
    current_task: Optional[str]
    completed_tasks: int
    failed_tasks: int
    last_active: float
    capabilities: List[str]


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the CESARE 2.0 system.
    """
    
    def __init__(self, agent_id: str, capabilities: List[str]):
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.state = AgentState(
            status='idle',
            current_task=None,
            completed_tasks=0,
            failed_tasks=0,
            last_active=time.time(),
            capabilities=capabilities
        )
        self.message_queue = asyncio.Queue()
        self.running = False
    
    @abstractmethod
    async def process_message(self, message: ParsedMessage) -> Dict[str, Any]:
        """
        Process a parsed message and return a response.
        
        Args:
            message: ParsedMessage object
            
        Returns:
            Dictionary containing response data
        """
        pass
    
    @abstractmethod
    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific task based on parsed information.
        
        Args:
            task_data: Task data extracted from message
            
        Returns:
            Dictionary containing execution results
        """
        pass
    
    async def handle_message(self, message: ParsedMessage):
        """Handle incoming message."""
        await self.message_queue.put(message)
        self.state.last_active = time.time()
    
    async def run(self):
        """Main agent loop."""
        self.running = True
        while self.running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(), 
                    timeout=1.0
                )
                
                self.state.status = 'processing'
                self.state.current_task = message.message_id
                
                try:
                    response = await self.process_message(message)
                    
                    if message.message_type == MessageType.TASK:
                        result = await self.execute_task(response)
                        self.state.completed_tasks += 1
                    else:
                        result = response
                    
                    self.state.status = 'idle'
                    self.state.current_task = None
                    
                except Exception as e:
                    self.state.failed_tasks += 1
                    self.state.status = 'error'
                    result = {
                        'error': str(e),
                        'message_id': message.message_id
                    }
                
                self.message_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
    
    def stop(self):
        """Stop the agent."""
        self.running = False
    
    def get_state(self) -> AgentState:
        """Get current agent state."""
        return self.state


class CoderAgent(BaseAgent):
    """
    Specialized agent for code generation and manipulation.
    """
    
    def __init__(self):
        super().__init__('coder', [
            'python', 'javascript', 'task_component', 
            'code_reference', 'file_path'
        ])
    
    async def process_message(self, message: ParsedMessage) -> Dict[str, Any]:
        """Process coding-related messages."""
        response = {
            'agent_id': self.agent_id,
            'message_id': message.message_id,
            'actions': []
        }
        
        # Analyze semantic tokens for coding tasks
        for token in message.semantic_tokens:
            if token.token_type == 'task_component':
                action = self._plan_coding_action(token)
                response['actions'].append(action)
            elif token.token_type == 'file_path':
                response['files'] = response.get('files', [])
                response['files'].append(token.value)
        
        return response
    
    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute coding task."""
        # Placeholder for actual code generation logic
        return {
            'status': 'completed',
            'generated_code': '# Code generated by CoderAgent',
            'files_modified': task_data.get('files', [])
        }
    
    def _plan_coding_action(self, token: SemanticToken) -> Dict[str, Any]:
        """Plan a coding action based on token."""
        return {
            'type': 'code_generation',
            'action': token.metadata.get('action', 'unknown'),
            'context': token.value,
            'confidence': token.confidence
        }


class AnalystAgent(BaseAgent):
    """
    Specialized agent for data analysis and intent recognition.
    """
    
    def __init__(self):
        super().__init__('analyst', [
            'data_analysis', 'intent', 'code_reference',
            'pattern_recognition'
        ])
    
    async def process_message(self, message: ParsedMessage) -> Dict[str, Any]:
        """Process analysis-related messages."""
        response = {
            'agent_id': self.agent_id,
            'message_id': message.message_id,
            'intents': [],
            'entities': []
        }
        
        # Extract intents and entities
        for token in message.semantic_tokens:
            if token.token_type == 'intent':
                response['intents'].append({
                    'type': token.value,
                    'confidence': token.confidence,
                    'keywords': token.metadata.get('keywords_found', [])
                })
            elif token.token_type in ['code_reference', 'file_path']:
                response['entities'].append({
                    'type': token.token_type,
                    'value': token.value,
                    'confidence': token.confidence
                })
        
        return response
    
    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute analysis task."""
        return {
            'status': 'completed',
            'analysis': {
                'intents_found': len(task_data.get('intents', [])),
                'entities_found': len(task_data.get('entities', []))
            }
        }


class ReviewerAgent(BaseAgent):
    """
    Specialized agent for code review and validation.
    """
    
    def __init__(self):
        super().__init__('reviewer', [
            'validation', 'file_path', 'quality_check',
            'security_review'
        ])
    
    async def process_message(self, message: ParsedMessage) -> Dict[str, Any]:
        """Process review-related messages."""
        response = {
            'agent_id': self.agent_id,
            'message_id': message.message_id,
            'review_items': []
        }
        
        # Identify items to review
        for token in message.semantic_tokens:
            if token.token_type == 'file_path':
                response['review_items'].append({
                    'type': 'file',
                    'path': token.value,
                    'review_type': 'comprehensive'
                })
            elif token.token_type == 'code_reference':
                response['review_items'].append({
                    'type': 'code',
                    'reference': token.value,
                    'review_type': 'security'
                })
        
        return response
    
    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute review task."""
        return {
            'status': 'completed',
            'review_results': {
                'items_reviewed': len(task_data.get('review_items', [])),
                'issues_found': 0,
                'recommendations': []
            }
        }


class CoordinatorAgent(BaseAgent):
    """
    Specialized agent for coordinating tasks between other agents.
    """
    
    def __init__(self):
        super().__init__('coordinator', [
            'orchestration', 'task_decomposition',
            'load_balancing', 'priority_management'
        ])
        self.registered_agents = {}
    
    async def process_message(self, message: ParsedMessage) -> Dict[str, Any]:
        """Process coordination messages."""
        response = {
            'agent_id': self.agent_id,
            'message_id': message.message_id,
            'coordination_plan': []
        }
        
        # Create coordination plan based on dependencies
        if message.dependencies:
            response['coordination_plan'].append({
                'type': 'dependency_resolution',
                'dependencies': message.dependencies,
                'strategy': 'sequential'
            })
        
        # Plan parallel execution if possible
        if message.execution_hints.get('parallelizable'):
            response['coordination_plan'].append({
                'type': 'parallel_execution',
                'estimated_workers': 2,
                'strategy': 'load_balanced'
            })
        
        return response
    
    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute coordination task."""
        return {
            'status': 'completed',
            'coordination_results': {
                'plan_created': len(task_data.get('coordination_plan', [])),
                'agents_assigned': list(self.registered_agents.keys())
            }
        }
    
    def register_agent(self, agent_id: str, capabilities: List[str]):
        """Register another agent with the coordinator."""
        self.registered_agents[agent_id] = {
            'capabilities': capabilities,
            'status': 'active'
        }


class AgentFactory:
    """Factory for creating specialized agents."""
    
    _agent_types = {
        'coder': CoderAgent,
        'analyst': AnalystAgent,
        'reviewer': ReviewerAgent,
        'coordinator': CoordinatorAgent
    }
    
    @classmethod
    def create_agent(cls, agent_type: str) -> BaseAgent:
        """Create an agent of the specified type."""
        if agent_type not in cls._agent_types:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        return cls._agent_types[agent_type]()
    
    @classmethod
    def get_available_types(cls) -> List[str]:
        """Get list of available agent types."""
        return list(cls._agent_types.keys())


# Example usage
async def main():
    """Test the agent system."""
    # Create agents
    coder = AgentFactory.create_agent('coder')
    analyst = AgentFactory.create_agent('analyst')
    reviewer = AgentFactory.create_agent('reviewer')
    coordinator = AgentFactory.create_agent('coordinator')
    
    # Start agents
    agents = [coder, analyst, reviewer, coordinator]
    tasks = [asyncio.create_task(agent.run()) for agent in agents]
    
    # Create test message
    from .parsing_engine import AdvancedParser
    parser = AdvancedParser()
    
    test_message_data = {
        'sender': 'user',
        'content': 'Create a Python script to analyze data files in /data folder.',
        'type': 'task',
        'priority': 'high'
    }
    
    parsed_message = await parser.parse_stream(test_message_data)
    
    # Send message to appropriate agent
    await analyst.handle_message(parsed_message)
    
    # Let agents process for a bit
    await asyncio.sleep(2)
    
    # Stop agents
    for agent in agents:
        agent.stop()
    
    # Wait for tasks to complete
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("Agent system test completed")


if __name__ == '__main__':
    asyncio.run(main())
