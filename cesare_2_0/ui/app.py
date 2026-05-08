"""
CESARE 2.0 - Streamlit UI

Modern web interface for the CESARE 2.0 multi-agent system with advanced parsing.
"""

import streamlit as st
import asyncio
import time
from typing import Dict, Any
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import Orchestrator
from core.parsing_engine import MessageType, Priority


class CESAREUI:
    """Streamlit UI for CESARE 2.0."""
    
    def __init__(self):
        self.orchestrator = None
        self.system_running = False
    
    def initialize_system(self):
        """Initialize the CESARE 2.0 system."""
        if self.orchestrator is None:
            # Initialize with debug disabled by default - user can enable via UI
            self.orchestrator = Orchestrator(debug_enabled=False)
            # Note: initialize_agents() might not exist in the new orchestrator
            # Commented out to avoid errors - agents are managed internally
            # self.orchestrator.initialize_agents()
    
    async def start_system(self):
        """Start the orchestrator."""
        if self.orchestrator and not self.system_running:
            await self.orchestrator.start()
            self.system_running = True
    
    async def stop_system(self):
        """Stop the orchestrator."""
        if self.orchestrator and self.system_running:
            await self.orchestrator.stop()
            self.system_running = False
    
    def render_sidebar(self):
        """Render sidebar with controls."""
        st.sidebar.title("CESARE 2.0")
        st.sidebar.markdown("---")
        
        # System controls
        st.sidebar.subheader("System Controls")
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("▶️ Start", use_container_width=True):
                self.initialize_system()
                asyncio.run(self.start_system())
                st.session_state.system_started = True
                st.success("System started!")
                st.rerun()
        
        with col2:
            if st.button("⏹️ Stop", use_container_width=True):
                if self.system_running:
                    asyncio.run(self.stop_system())
                    st.session_state.system_started = False
                    st.success("System stopped!")
                    st.rerun()
        
        st.sidebar.markdown("---")
        
        # Debug controls
        st.sidebar.subheader("Debug Options")
        
        if self.orchestrator:
            debug_enabled = st.session_state.get('debug_enabled', False)
            
            # Show enable button
            if not debug_enabled:
                if st.button("🐛 Enable Debug", 
                            use_container_width=True,
                            disabled=not self.system_running):
                    if self.system_running:
                        self.orchestrator.enable_debug()
                        st.session_state.debug_enabled = True
                        st.success("Debug logging enabled! You can now see agent messages.")
                        st.rerun()
            else:
                # Debug is enabled - show status and controls
                st.success("✅ Debug Enabled")
                
                if st.button("🗑️ Clear Debug Log", use_container_width=True):
                    self.orchestrator.clear_debug_messages()
                    st.success("Debug log cleared")
                    st.rerun()
                
                # Show debug info in sidebar
                debug_data = self.orchestrator.get_debug_messages()
                if debug_data['total_messages'] > 0:
                    st.sidebar.markdown(f"**Messages logged:** {debug_data['total_messages']}")
        
        st.sidebar.markdown("---")
        
        # System status
        st.sidebar.subheader("System Status")
        if self.system_running and self.orchestrator:
            metrics = self.orchestrator.get_metrics()
            st.sidebar.metric("Active Agents", metrics.active_agents)
            st.sidebar.metric("Total Messages", metrics.total_messages)
            st.sidebar.metric("Successful Tasks", metrics.successful_tasks)
            st.sidebar.metric("Failed Tasks", metrics.failed_tasks)
            
            if metrics.messages_per_second > 0:
                st.sidebar.metric("Msg/sec", f"{metrics.messages_per_second:.2f}")
        else:
            st.sidebar.info("System not running")
        
        st.sidebar.markdown("---")
        
        # Agent status
        if self.system_running and self.orchestrator:
            st.sidebar.subheader("Agent States")
            agent_states = self.orchestrator.get_agent_states()
            for agent_id, state in agent_states.items():
                status_emoji = {
                    'idle': '🟢',
                    'processing': '🟡',
                    'error': '🔴'
                }.get(state['status'], '⚪')
                
                st.sidebar.text(f"{status_emoji} {agent_id}")
    
    def render_main_chat(self):
        """Render main chat interface."""
        st.title("💬 CESARE 2.0 - Advanced Multi-Agent System")
        st.markdown("### Intelligent Task Processing with Semantic Parsing")
        
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if "metadata" in message:
                    with st.expander("View parsing details"):
                        st.json(message["metadata"])
        
        # Chat input
        if prompt := st.chat_input("Describe your task or ask a question..."):
            # Add user message to chat history
            st.session_state.messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Process message
            if self.system_running and self.orchestrator:
                with st.chat_message("assistant"):
                    with st.spinner("Processing with AI agents..."):
                        try:
                            # Submit request
                            request_data = {
                                'sender': 'user',
                                'content': prompt,
                                'type': 'task' if any(kw in prompt.lower() 
                                                   for kw in ['create', 'make', 'build', 'analyze']) 
                                        else 'query',
                                'priority': 'high' if any(kw in prompt.lower() 
                                                        for kw in ['urgent', 'important', 'critical']) 
                                         else 'normal'
                            }
                            
                            # Parse and process
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            parsed_msg = loop.run_until_complete(
                                self.orchestrator.parser.parse_stream(request_data)
                            )
                            
                            # Execute task
                            result = loop.run_until_complete(
                                self.orchestrator.execute_task({
                                    'description': prompt,
                                    'priority': request_data['priority'],
                                    'timeout': 30.0
                                })
                            )
                            
                            loop.close()
                            
                            # Generate response
                            response = f"✅ Task processed successfully!\n\n"
                            response += f"**Agent:** {result.agent_id}\n"
                            response += f"**Status:** {result.status}\n"
                            response += f"**Execution time:** {result.execution_time:.2f}s\n"
                            
                            if result.dependencies_resolved:
                                response += f"\n**Dependencies resolved:** {len(result.dependencies_resolved)}\n"
                            
                            # Metadata for parsing details
                            metadata = {
                                'message_id': parsed_msg.message_id,
                                'semantic_tokens': len(parsed_msg.semantic_tokens),
                                'token_types': list(set(t.token_type for t in parsed_msg.semantic_tokens)),
                                'execution_hints': parsed_msg.execution_hints,
                                'context_chain_length': len(parsed_msg.context_chain)
                            }
                            
                            st.markdown(response)
                            
                            # Add assistant message to history
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": response,
                                "metadata": metadata
                            })
                            
                        except Exception as e:
                            error_msg = f"❌ Error processing request: {str(e)}"
                            st.markdown(error_msg)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": error_msg
                            })
            else:
                with st.chat_message("assistant"):
                    warning = "⚠️ System is not running. Please start the system from the sidebar."
                    st.markdown(warning)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": warning
                    })
    
    def render_analytics(self):
        """Render analytics dashboard."""
        st.title("📊 Analytics Dashboard")
        
        if not self.system_running or not self.orchestrator:
            st.warning("Please start the system to view analytics")
            return
        
        metrics = self.orchestrator.get_metrics()
        
        # Top-level metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Messages",
                metrics.total_messages,
                delta=None
            )
        
        with col2:
            success_rate = (
                (metrics.successful_tasks / metrics.total_tasks * 100) 
                if metrics.total_tasks > 0 else 0
            )
            st.metric(
                "Success Rate",
                f"{success_rate:.1f}%",
                delta=None
            )
        
        with col3:
            st.metric(
                "Avg Execution Time",
                f"{metrics.average_execution_time:.2f}s",
                delta=None
            )
        
        with col4:
            st.metric(
                "Throughput",
                f"{metrics.messages_per_second:.2f} msg/s",
                delta=None
            )
        
        st.markdown("---")
        
        # Agent performance
        st.subheader("Agent Performance")
        agent_states = self.orchestrator.get_agent_states()
        
        for agent_id, state in agent_states.items():
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(f"{agent_id} Status", state['status'])
            
            with col2:
                st.metric("Completed", state['completed_tasks'])
            
            with col3:
                st.metric("Failed", state['failed_tasks'])
            
            with col4:
                last_active = time.time() - state['last_active']
                st.metric("Last Active", f"{last_active:.0f}s ago")
        
        st.markdown("---")
        
        # Task results
        st.subheader("Recent Task Results")
        task_results = self.orchestrator.task_results
        
        if task_results:
            for task_id, result in list(task_results.items())[-5:]:
                with st.expander(f"Task {task_id[:8]}... - {result.status}"):
                    st.write(f"**Agent:** {result.agent_id}")
                    st.write(f"**Execution Time:** {result.execution_time:.2f}s")
                    st.write(f"**Dependencies:** {len(result.dependencies_resolved)}")
                    st.json(result.result)
        else:
            st.info("No tasks executed yet")
    
    def render_debug_log(self):
        """Render debug log showing messages between Cesare and agents."""
        st.title("🐛 Debug Log - Agent Communications")
        st.markdown("""
        Questa sezione mostra tutti i messaggi scambiati tra **Cesare** (l'orchestratore) 
        e gli **agenti**. Utile per il debugging e capire dove si verificano eventuali problemi.
        """)
        
        if not self.orchestrator:
            st.warning("Orchestrator non inizializzato. Avvia il sistema dalla sidebar.")
            return
        
        # Check if debug is enabled
        debug_enabled = self.orchestrator.is_debug_enabled()
        
        if not debug_enabled:
            st.warning("""
            ⚠️ **Debug non abilitato!**
            
            Per visualizzare i messaggi tra Cesare e gli agenti:
            1. Assicurati che il sistema sia avviato
            2. Clicca su **🐛 Enable Debug** nella sidebar
            3. Esegui un task e torna a questa pagina per vedere i messaggi
            """)
            return
        
        # Get debug messages
        debug_data = self.orchestrator.get_debug_messages()
        
        if debug_data['total_messages'] == 0:
            st.info("Nessun messaggio di debug registrato ancora. Esegui un task per iniziare.")
            return
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        
        to_agent_count = len([m for m in debug_data['messages'] if m['direction'] == 'TO_AGENT'])
        from_agent_count = len([m for m in debug_data['messages'] if m['response_content']])
        error_count = len([m for m in debug_data['messages'] if m['status'] == 'error'])
        
        with col1:
            st.metric("Messaggi inviati agli agenti", to_agent_count)
        with col2:
            st.metric("Risposte ricevute", from_agent_count)
        with col3:
            st.metric("Errori", error_count, delta="⚠️" if error_count > 0 else "✅")
        
        st.markdown("---")
        
        # Filter options
        st.subheader("Filtra messaggi")
        col1, col2 = st.columns(2)
        
        with col1:
            filter_agent = st.multiselect(
                "Filtra per Agente",
                options=list(set(m['agent_id'] for m in debug_data['messages']))
            )
        
        with col2:
            filter_status = st.selectbox(
                "Filtra per Stato",
                options=["Tutti", "success", "error", "sent"]
            )
        
        # Display messages
        st.markdown("---")
        st.subheader("Messaggi")
        
        filtered_messages = debug_data['messages']
        
        if filter_agent:
            filtered_messages = [m for m in filtered_messages if m['agent_id'] in filter_agent]
        
        if filter_status != "Tutti":
            filtered_messages = [m for m in filtered_messages if m['status'] == filter_status]
        
        # Group messages by conversation (TO_AGENT followed by FROM_AGENT)
        conversations = {}
        for msg in filtered_messages:
            key = f"{msg['agent_id']}_{msg['task_description']}"
            if key not in conversations:
                conversations[key] = {'to': None, 'from': None, 'error': None}
            
            if msg['direction'] == 'TO_AGENT':
                conversations[key]['to'] = msg
            elif msg['direction'] == 'FROM_AGENT' or msg['direction'] == 'ERROR':
                if msg['status'] == 'error':
                    conversations[key]['error'] = msg
                else:
                    conversations[key]['from'] = msg
        
        # Display each conversation
        for idx, (key, conv) in enumerate(conversations.items()):
            agent_id = conv['to']['agent_id'] if conv['to'] else "Unknown"
            task_desc = conv['to']['task_description'] if conv['to'] else "Unknown"
            
            with st.expander(f"**{idx + 1}. Agente: {agent_id}** - {task_desc}", expanded=False):
                # Message TO agent
                if conv['to']:
                    st.markdown("#### 📤 Messaggio da Cesare all'Agente")
                    st.json({
                        "timestamp": conv['to']['timestamp'],
                        "agent_id": conv['to']['agent_id'],
                        "task": conv['to']['task_description'],
                        "content": conv['to']['message_content']
                    })
                
                # Response FROM agent
                if conv['from']:
                    st.markdown("#### 📥 Risposta dall'Agente a Cesare")
                    st.success(f"Status: **{conv['from']['status']}** | Tempo: **{conv['from']['execution_time_ms']:.2f}ms**")
                    st.json({
                        "timestamp": conv['from']['timestamp'],
                        "agent_id": conv['from']['agent_id'],
                        "response": conv['from']['response_content']
                    })
                
                # Error
                if conv['error']:
                    st.markdown("#### ❌ Errore nella comunicazione")
                    st.error(f"Status: **{conv['error']['status']}** | Tempo: **{conv['error']['execution_time_ms']:.2f}ms**")
                    st.json({
                        "timestamp": conv['error']['timestamp'],
                        "agent_id": conv['error']['agent_id'],
                        "error": conv['error']['message_content']
                    })
        
        # Raw data export option
        st.markdown("---")
        st.subheader("Export Dati")
        if st.button("📥 Scarica log completo (JSON)"):
            import json
            json_str = json.dumps(debug_data, indent=2)
            st.download_button(
                label="Download JSON",
                data=json_str,
                file_name=f"debug_log_{time.strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    def render(self):
        """Render the complete UI."""
        # Page configuration
        st.set_page_config(
            page_title="CESARE 2.0",
            page_icon="🤖",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Render sidebar
        self.render_sidebar()
        
        # Main content with tabs
        tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Analytics", "🐛 Debug Log"])
        
        with tab1:
            self.render_main_chat()
        
        with tab2:
            self.render_analytics()
        
        with tab3:
            self.render_debug_log()


def main():
    """Main entry point."""
    ui = CESAREUI()
    ui.render()


if __name__ == "__main__":
    main()
