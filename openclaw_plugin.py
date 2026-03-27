"""Brain Guard OpenClaw Plugin Wrapper.

This module provides the OpenClaw plugin interface for Brain Guard,
enabling integration with OpenClaw's message flow.
"""

import os
import sys
import asyncio
import logging
from typing import Any, Optional, Dict, List

# Import from the src package
from src import BrainGuardPlugin, get_plugin, initialize_plugin

logger = logging.getLogger(__name__)


class OpenClawBrainGuardPlugin:
    """
    OpenClaw plugin wrapper for Brain Guard.
    
    This class implements the OpenClaw plugin interface with hooks for:
    - onMessage: Preprocess messages before sending to AI
    - onResponse: Monitor AI responses for coherence
    """
    
    def __init__(self):
        """Initialize the OpenClaw plugin wrapper."""
        self._plugin: Optional[BrainGuardPlugin] = None
        self._initialized = False
        self._config_path = os.environ.get(
            "BRAIN_GUARD_CONFIG",
            os.path.join(os.path.dirname(__file__), "config", "brain_guard.yaml")
        )
        
    async def initialize(self) -> None:
        """Initialize the Brain Guard plugin."""
        try:
            logger.info("Initializing Brain Guard OpenClaw plugin...")
            
            # Set default environment variable if not present
            if not os.environ.get("BRAIN_GUARD_ENABLED"):
                os.environ["BRAIN_GUARD_ENABLED"] = "true"
            
            # Get or create plugin instance
            self._plugin = get_plugin(self._config_path)
            await self._plugin.initialize()
            
            self._initialized = True
            logger.info("Brain Guard OpenClaw plugin initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Brain Guard plugin: {e}")
            # Don't fail OpenClaw startup if plugin fails
            self._initialized = False
    
    async def shutdown(self) -> None:
        """Shutdown the plugin gracefully."""
        if self._plugin:
            await self._plugin.shutdown()
            self._initialized = False
            logger.info("Brain Guard OpenClaw plugin shutdown complete")
    
    async def onMessage(
        self,
        message: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        OpenClaw hook: Called before sending message to AI.
        
        Args:
            message: The message dictionary containing 'content', 'role', etc.
            context: Optional session context
            
        Returns:
            Modified message dictionary with Brain Guard preprocessing
        """
        if not self._initialized or not self._plugin:
            return message
        
        try:
            # Extract session ID from context or generate one
            session_id = self._extract_session_id(context)
            
            # Get user message content
            user_message = message.get("content", "")
            if not user_message:
                return message
            
            # Preprocess through Brain Guard
            result = await self._plugin.preprocess_message(
                session_id=session_id,
                user_message=user_message,
                context=context
            )
            
            # Update message with conditioned input
            conditioned_input = result.get("conditioned_input", user_message)
            metadata = result.get("metadata", {})
            
            # Add Brain Guard metadata to message
            if "brain_guard" not in message:
                message["brain_guard"] = {}
            
            message["brain_guard"]["preprocessed"] = True
            message["brain_guard"]["metadata"] = metadata
            
            # Update content if preprocessing modified it
            if conditioned_input != user_message:
                message["content"] = conditioned_input
                message["brain_guard"]["modified"] = True
            
            return message
            
        except Exception as e:
            logger.error(f"Error in onMessage hook: {e}")
            # Return original message on error
            return message
    
    async def onResponse(
        self,
        response: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        OpenClaw hook: Called after receiving response from AI.
        
        Args:
            response: The response dictionary containing 'content', etc.
            context: Optional session context with original message info
            
        Returns:
            Modified response with Brain Guard coherence monitoring
        """
        if not self._initialized or not self._plugin:
            return response
        
        try:
            # Extract session ID from context
            session_id = self._extract_session_id(context)
            
            # Get AI response content
            response_text = response.get("content", "")
            
            # Get preprocessing metadata if available
            preprocess_metadata = None
            if context and "brain_guard" in context:
                preprocess_metadata = context["brain_guard"].get("metadata")
            
            # Monitor response through Brain Guard
            result = await self._plugin.monitor_response(
                session_id=session_id,
                response=response_text,
                metadata=preprocess_metadata
            )
            
            # Add Brain Guard monitoring results to response
            if "brain_guard" not in response:
                response["brain_guard"] = {}
            
            response["brain_guard"]["monitored"] = True
            response["brain_guard"]["metrics"] = result.get("metrics", {})
            response["brain_guard"]["intervention"] = result.get("intervention")
            response["brain_guard"]["anchors"] = result.get("anchors", [])
            response["brain_guard"]["contradictions"] = result.get("contradictions", [])
            response["brain_guard"]["timing"] = result.get("timing", {})
            
            # Log if intervention was triggered
            intervention = result.get("intervention")
            if intervention:
                logger.warning(
                    f"Brain Guard intervention triggered for session {session_id}: "
                    f"{intervention.get('type', 'unknown')}"
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error in onResponse hook: {e}")
            # Return original response on error
            return response
    
    def _extract_session_id(self, context: Optional[Dict[str, Any]]) -> str:
        """Extract session ID from context or generate a default."""
        if context:
            # Try various common session ID fields
            for key in ["session_id", "sessionId", "conversation_id", "chat_id", "id"]:
                if key in context:
                    return str(context[key])
        
        # Generate a default session ID
        import uuid
        return f"bg_{uuid.uuid4().hex[:16]}"
    
    def get_health(self) -> Dict[str, Any]:
        """Get plugin health status."""
        return {
            "initialized": self._initialized,
            "enabled": self._plugin.enabled if self._plugin else False,
            "plugin": "brain-guard",
            "version": "1.0.0"
        }


# Singleton instance
_plugin_instance: Optional[OpenClawBrainGuardPlugin] = None


def get_openclaw_plugin() -> OpenClawBrainGuardPlugin:
    """Get or create the singleton OpenClaw plugin instance."""
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = OpenClawBrainGuardPlugin()
    return _plugin_instance


# OpenClaw plugin interface exports
async def initialize() -> None:
    """Initialize the plugin (called by OpenClaw on startup)."""
    plugin = get_openclaw_plugin()
    await plugin.initialize()


async def shutdown() -> None:
    """Shutdown the plugin (called by OpenClaw on shutdown)."""
    plugin = get_openclaw_plugin()
    await plugin.shutdown()


async def onMessage(message: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process message before sending to AI (called by OpenClaw)."""
    plugin = get_openclaw_plugin()
    return await plugin.onMessage(message, context)


async def onResponse(response: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process response after receiving from AI (called by OpenClaw)."""
    plugin = get_openclaw_plugin()
    return await plugin.onResponse(response, context)


def health() -> Dict[str, Any]:
    """Get plugin health status (called by OpenClaw)."""
    plugin = get_openclaw_plugin()
    return plugin.get_health()
