#!/usr/bin/env python3
"""
Fake AI Provider for SoloPilot

Implements the BaseProvider interface with deterministic fake responses.
Used for offline testing and CI environments without requiring real LLM access.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.ai_providers.base import BaseProvider, log_call


class FakeProvider(BaseProvider):
    """Fake provider that generates deterministic stub code for testing."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize fake provider.
        
        Args:
            config: Optional configuration (ignored for fake provider)
        """
        self.config = config or {}
        self.call_count = 0
        self.last_cost_info = None

    @log_call
    def generate_code(self, prompt: str, files: Optional[List[Path]] = None, timeout: Optional[int] = None) -> str:
        """
        Generate fake code based on prompt patterns.
        
        Args:
            prompt: The instruction prompt for code generation
            files: Optional list of file paths (used for context awareness)
            timeout: Optional timeout in seconds (ignored for fake provider)
            
        Returns:
            Generated fake code as a string
        """
        self.call_count += 1
        
        # Extract language/technology hints from prompt and files
        language = self._infer_language(prompt, files)
        
        # Generate fake response based on language
        if language == "javascript":
            return self._generate_javascript_response(prompt)
        elif language == "typescript":
            return self._generate_typescript_response(prompt)
        elif language == "python":
            return self._generate_python_response(prompt)
        elif language == "java":
            return self._generate_java_response(prompt)
        else:
            return self._generate_generic_response(prompt, language)

    def is_available(self) -> bool:
        """
        Fake provider is always available.
        
        Returns:
            Always True
        """
        return True

    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about the fake provider.
        
        Returns:
            Dictionary with provider metadata
        """
        return {
            "name": "fake",
            "display_name": "Fake Provider (Testing)",
            "available": True,
            "model": "fake-model-v1",
            "call_count": self.call_count,
            "description": "Deterministic fake responses for offline testing"
        }

    def get_cost_info(self) -> Optional[Dict[str, Any]]:
        """
        Get fake cost information.
        
        Returns:
            Dictionary with fake cost data
        """
        return {
            "timestamp": time.time(),
            "model": "fake-model-v1",
            "tokens_in": len(self._last_prompt.split()) if hasattr(self, '_last_prompt') else 50,
            "tokens_out": 100,
            "latency_ms": 50,  # Fake 50ms latency
            "cost_usd": 0.0  # Free fake calls
        }

    def _infer_language(self, prompt: str, files: Optional[List[Path]] = None) -> str:
        """
        Infer programming language from prompt and file context.
        
        Args:
            prompt: The prompt text
            files: Optional file paths for context
            
        Returns:
            Inferred language name
        """
        prompt_lower = prompt.lower()
        
        # Check file extensions if provided
        if files:
            for file_path in files:
                ext = file_path.suffix.lower()
                if ext in ['.js', '.jsx']:
                    return "javascript"
                elif ext in ['.ts', '.tsx']:
                    return "typescript"
                elif ext in ['.py']:
                    return "python"
                elif ext in ['.java']:
                    return "java"
                elif ext in ['.go']:
                    return "go"
                elif ext in ['.rs']:
                    return "rust"
        
        # Check prompt content for language indicators
        if any(keyword in prompt_lower for keyword in ['react', 'node.js', 'express', 'javascript', 'npm']):
            return "javascript"
        elif any(keyword in prompt_lower for keyword in ['typescript', 'angular', 'next.js']):
            return "typescript"
        elif any(keyword in prompt_lower for keyword in ['python', 'django', 'flask', 'fastapi', 'pip']):
            return "python"
        elif any(keyword in prompt_lower for keyword in ['java', 'spring', 'maven', 'gradle']):
            return "java"
        elif any(keyword in prompt_lower for keyword in ['golang', 'go lang']):
            return "go"
        elif any(keyword in prompt_lower for keyword in ['rust', 'cargo']):
            return "rust"
        
        # Default to JavaScript for web projects
        return "javascript"

    def _generate_javascript_response(self, prompt: str) -> str:
        """Generate fake JavaScript code response."""
        self._last_prompt = prompt
        
        # Extract task name from prompt
        task_name = self._extract_task_name(prompt)
        
        return f'''```javascript
// === SKELETON CODE ===
// Fake implementation for: {task_name}
class {task_name.replace(" ", "")}Implementation {{
    constructor() {{
        // TODO: Initialize {task_name.lower()}
        this.initialized = false;
    }}
    
    async execute() {{
        // TODO: Implement {task_name.lower()} functionality
        console.log("Executing {task_name.lower()}...");
        this.initialized = true;
        return {{ success: true, message: "Fake implementation completed" }};
    }}
    
    validate() {{
        // TODO: Add validation logic
        return this.initialized;
    }}
}}

module.exports = {task_name.replace(" ", "")}Implementation;

// === UNIT TEST ===
const {task_name.replace(" ", "")}Implementation = require('./{task_name.replace(" ", "").lower()}');

describe('{task_name}Implementation', () => {{
    let implementation;
    
    beforeEach(() => {{
        implementation = new {task_name.replace(" ", "")}Implementation();
    }});
    
    test('should initialize correctly', () => {{
        expect(implementation).toBeDefined();
        expect(implementation.initialized).toBe(false);
    }});
    
    test('should execute successfully', async () => {{
        const result = await implementation.execute();
        expect(result.success).toBe(true);
        expect(implementation.initialized).toBe(true);
    }});
    
    test('should validate correctly', () => {{
        expect(implementation.validate()).toBe(false);
        implementation.initialized = true;
        expect(implementation.validate()).toBe(true);
    }});
}});
```'''

    def _generate_typescript_response(self, prompt: str) -> str:
        """Generate fake TypeScript code response."""
        self._last_prompt = prompt
        task_name = self._extract_task_name(prompt)
        
        return f'''```typescript
// === SKELETON CODE ===
// Fake implementation for: {task_name}
interface I{task_name.replace(" ", "")} {{
    execute(): Promise<ExecutionResult>;
    validate(): boolean;
}}

interface ExecutionResult {{
    success: boolean;
    message: string;
    data?: any;
}}

class {task_name.replace(" ", "")}Implementation implements I{task_name.replace(" ", "")} {{
    private initialized: boolean = false;
    
    constructor() {{
        // TODO: Initialize {task_name.lower()}
    }}
    
    async execute(): Promise<ExecutionResult> {{
        // TODO: Implement {task_name.lower()} functionality
        console.log("Executing {task_name.lower()}...");
        this.initialized = true;
        return {{ 
            success: true, 
            message: "Fake implementation completed" 
        }};
    }}
    
    validate(): boolean {{
        // TODO: Add validation logic
        return this.initialized;
    }}
}}

export {{ {task_name.replace(" ", "")}Implementation, I{task_name.replace(" ", "")}, ExecutionResult }};

// === UNIT TEST ===
import {{ {task_name.replace(" ", "")}Implementation }} from './{task_name.replace(" ", "").lower()}';

describe('{task_name}Implementation', () => {{
    let implementation: {task_name.replace(" ", "")}Implementation;
    
    beforeEach(() => {{
        implementation = new {task_name.replace(" ", "")}Implementation();
    }});
    
    test('should initialize correctly', () => {{
        expect(implementation).toBeDefined();
        expect(implementation.validate()).toBe(false);
    }});
    
    test('should execute successfully', async () => {{
        const result = await implementation.execute();
        expect(result.success).toBe(true);
        expect(implementation.validate()).toBe(true);
    }});
}});
```'''

    def _generate_python_response(self, prompt: str) -> str:
        """Generate fake Python code response."""
        self._last_prompt = prompt
        task_name = self._extract_task_name(prompt)
        class_name = task_name.replace(" ", "")
        
        return f'''```python
# === SKELETON CODE ===
# Fake implementation for: {task_name}
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class {class_name}Implementation:
    """Fake implementation for {task_name.lower()}."""
    
    def __init__(self):
        """Initialize {task_name.lower()}."""
        # TODO: Initialize {task_name.lower()}
        self.initialized = False
        logger.info("Initializing {task_name.lower()} implementation")
    
    async def execute(self) -> Dict[str, Any]:
        """
        Execute {task_name.lower()} functionality.
        
        Returns:
            Dict containing execution result
        """
        # TODO: Implement {task_name.lower()} functionality
        logger.info("Executing {task_name.lower()}...")
        self.initialized = True
        return {{
            "success": True,
            "message": "Fake implementation completed"
        }}
    
    def validate(self) -> bool:
        """
        Validate {task_name.lower()} state.
        
        Returns:
            True if valid, False otherwise
        """
        # TODO: Add validation logic
        return self.initialized

# === UNIT TEST ===
import pytest
from unittest.mock import Mock, patch

class Test{class_name}Implementation:
    """Test cases for {class_name}Implementation."""
    
    @pytest.fixture
    def implementation(self):
        """Create implementation instance for testing."""
        return {class_name}Implementation()
    
    def test_initialization(self, implementation):
        """Test that implementation initializes correctly."""
        assert implementation is not None
        assert implementation.initialized is False
    
    @pytest.mark.asyncio
    async def test_execute_success(self, implementation):
        """Test successful execution."""
        result = await implementation.execute()
        assert result["success"] is True
        assert implementation.initialized is True
    
    def test_validate(self, implementation):
        """Test validation functionality."""
        assert implementation.validate() is False
        implementation.initialized = True
        assert implementation.validate() is True
```'''

    def _generate_java_response(self, prompt: str) -> str:
        """Generate fake Java code response."""
        self._last_prompt = prompt
        task_name = self._extract_task_name(prompt)
        class_name = task_name.replace(" ", "")
        
        return f'''```java
// === SKELETON CODE ===
// Fake implementation for: {task_name}
package com.solopilot.implementation;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.logging.Logger;

public class {class_name}Implementation {{
    private static final Logger logger = Logger.getLogger({class_name}Implementation.class.getName());
    private boolean initialized = false;
    
    public {class_name}Implementation() {{
        // TODO: Initialize {task_name.lower()}
        logger.info("Initializing {task_name.lower()} implementation");
    }}
    
    public CompletableFuture<Map<String, Object>> execute() {{
        // TODO: Implement {task_name.lower()} functionality
        logger.info("Executing {task_name.lower()}...");
        this.initialized = true;
        
        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("message", "Fake implementation completed");
        
        return CompletableFuture.completedFuture(result);
    }}
    
    public boolean validate() {{
        // TODO: Add validation logic
        return this.initialized;
    }}
}}

// === UNIT TEST ===
import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.Map;
import java.util.concurrent.ExecutionException;

class {class_name}ImplementationTest {{
    private {class_name}Implementation implementation;
    
    @BeforeEach
    void setUp() {{
        implementation = new {class_name}Implementation();
    }}
    
    @Test
    void testInitialization() {{
        assertNotNull(implementation);
        assertFalse(implementation.validate());
    }}
    
    @Test
    void testExecuteSuccess() throws ExecutionException, InterruptedException {{
        Map<String, Object> result = implementation.execute().get();
        assertTrue((Boolean) result.get("success"));
        assertTrue(implementation.validate());
    }}
}}
```'''

    def _generate_generic_response(self, prompt: str, language: str) -> str:
        """Generate generic fake code response."""
        self._last_prompt = prompt
        task_name = self._extract_task_name(prompt)
        
        return f'''```{language}
// === SKELETON CODE ===
// Fake {language} implementation for: {task_name}
// TODO: Implement {task_name.lower()} functionality

function implement{task_name.replace(" ", "")}() {{
    // TODO: Add implementation logic here
    console.log("Fake implementation for {task_name.lower()}");
    return {{ success: true, message: "Fake implementation completed" }};
}}

// === UNIT TEST ===
// TODO: Add unit tests for {task_name.lower()}
function test{task_name.replace(" ", "")}() {{
    const result = implement{task_name.replace(" ", "")}();
    assert(result.success === true);
    console.log("Test passed: {task_name}");
}}
```'''

    def _extract_task_name(self, prompt: str) -> str:
        """
        Extract a meaningful task name from the prompt.
        
        Args:
            prompt: The input prompt
            
        Returns:
            Extracted task name
        """
        # Simple heuristics to extract task name from prompt
        prompt_lower = prompt.lower()
        
        # Look for common patterns
        if "implement" in prompt_lower:
            # Extract what comes after "implement"
            parts = prompt.split()
            for i, part in enumerate(parts):
                if part.lower() == "implement" and i + 1 < len(parts):
                    extracted = " ".join(parts[i+1:i+4]).strip().title()  # Take more words
                    return extracted if extracted else "Implementation Task"
        
        if "create" in prompt_lower:
            # Extract what comes after "create"
            parts = prompt.split()
            for i, part in enumerate(parts):
                if part.lower() == "create" and i + 1 < len(parts):
                    extracted = " ".join(parts[i+1:i+4]).strip().title()  # Take more words
                    return extracted if extracted else "Creation Task"
        
        # Look for milestone names in JSON format
        if "milestone" in prompt_lower:
            return "Milestone Task"
            
        # Default fallback
        words = prompt.split()[:3]  # Take first 3 words
        return " ".join(word.strip('.,!?:;') for word in words).title() or "Generic Task"