"""Magentic Orchestrator with data flow tracking and event handling."""
from typing import Dict, Optional, Any

from agent_framework import (
    MagenticAgentDeltaEvent,
    MagenticAgentMessageEvent,
    MagenticBuilder,
    MagenticCallbackEvent,
    MagenticCallbackMode,
    MagenticFinalResultEvent,
    MagenticOrchestratorMessageEvent,
    WorkflowOutputEvent,
    AgentThread,
)
from agent_framework.openai import OpenAIChatClient
from openai import AsyncAzureOpenAI

from config.config import config
from utils.logger_config import magentic_logger


class MagenticOrchestrator:
    """Coordinates multi-agent workflows with streaming event handling."""
    
    def __init__(self) -> None:
        self.workflow = None
        self.last_stream_agent_id: Optional[str] = None
        self.stream_line_open: bool = False
        self.agent_outputs: Dict[str, str] = {}
        self.thread: Optional[AgentThread] = None
        self.updated_thread: Optional[AgentThread] = None
    
    def build_workflow(self, agents_dict: Dict) -> None:
        """Build Magentic workflow with dynamic agents."""
        magentic_logger.info("\n" + "="*70)
        magentic_logger.info("Building Magentic Workflow")
        magentic_logger.info("="*70 + "\n")
        
        azure_client = AsyncAzureOpenAI(
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_VERSION,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        )
        
        self.workflow = (
            MagenticBuilder()
            .participants(**agents_dict)
            .on_event(self._on_event, mode=MagenticCallbackMode.STREAMING)
            .with_standard_manager(
                chat_client=OpenAIChatClient(model_id=config.Model, async_client=azure_client),
                max_round_count=10,
                max_stall_count=3,
                max_reset_count=2,
            )
            .build()
        )
        
        magentic_logger.info(" Magentic Workflow built")
        magentic_logger.info("="*70 + "\n")
    
    async def _on_event(self, event: MagenticCallbackEvent) -> None:
        """Handle workflow events with detailed logging."""
        if isinstance(event, MagenticOrchestratorMessageEvent):
            magentic_logger.info(f"\n[ORCHESTRATOR:{event.kind}]")
            magentic_logger.info(f"{getattr(event.message, 'text', '')}")
            magentic_logger.info("-" * 70)
            
        elif isinstance(event, MagenticAgentDeltaEvent):
            if self.last_stream_agent_id != event.agent_id or not self.stream_line_open:
                if self.stream_line_open:
                    magentic_logger.info("")
                magentic_logger.info(f"\n[{event.agent_id}] streaming: ")
                self.last_stream_agent_id = event.agent_id
                self.stream_line_open = True
            
        elif isinstance(event, MagenticAgentMessageEvent):
            if self.stream_line_open:
                self.stream_line_open = False
            
            if event.message:
                response_text = (event.message.text or "").strip()
                self.agent_outputs[event.agent_id] = response_text
                
                magentic_logger.info(f"\n[{event.agent_id}] {event.message.role.value}:")
                magentic_logger.info(f"{response_text[:500]}...")
                magentic_logger.info("-" * 70)
                
        elif isinstance(event, MagenticFinalResultEvent):
            magentic_logger.info("\n" + "="*70)
            magentic_logger.info("FINAL RESULT")
            magentic_logger.info("="*70)
            if event.message:
                magentic_logger.info(event.message.text)
            magentic_logger.info("="*70 + "\n")
    
    async def execute(self, query: str, thread: Optional[AgentThread] = None) -> str:
        """Execute workflow with enhanced data passing instructions and optional thread for session management."""
        self.thread = thread
        self.updated_thread = thread  # Initialize with provided thread
        
        magentic_logger.info(f"\n{'='*70}")
        magentic_logger.info(f"QUERY: {query}")
        if thread:
            magentic_logger.info(f"Using existing thread for session context")
        magentic_logger.info(f"{'='*70}\n")
        
        enhanced_query = f"""{query}
        IMPORTANT INSTRUCTIONS:
        - When Agent A retrieves data, it MUST include the actual data in its response
        - When Agent B needs to use data from Agent A, it should explicitly reference and use that data
        - DO NOT fetch new data from your own sources if data was already provided by another agent
        - Always confirm what data you received before processing it"""
        try:
            workflow_output = None
            # Pass thread to workflow if supported
            run_kwargs = {}
            if thread:
                # Try to pass thread to workflow if it supports it
                # Note: Magentic workflow might handle threads differently
                # For now, we'll store the thread and let the workflow use it if supported
                run_kwargs = {"thread": thread}
            
            async for event in self.workflow.run_stream(enhanced_query, **run_kwargs):
                if isinstance(event, WorkflowOutputEvent):
                    workflow_output = event
                    # Try to extract updated thread from workflow output if available
                    if hasattr(workflow_output, 'thread'):
                        self.updated_thread = workflow_output.thread
            
            if workflow_output:
                data = getattr(workflow_output, "data", None)
                result = getattr(data, "text", None) or (str(data) if data else "")
                
                magentic_logger.info("\n" + "="*70)
                magentic_logger.info("AGENT COLLABORATION SUMMARY")
                magentic_logger.info("="*70)
                for agent_id, output in self.agent_outputs.items():
                    magentic_logger.info(f"{agent_id}: {len(output)} characters output")
                magentic_logger.info("="*70 + "\n")
                
                return result
            return "Workflow completed without result"
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            magentic_logger.error(f"\n{'='*70}\nERROR\n{'='*70}\n{error_msg}\n{'='*70}\n")
            return error_msg