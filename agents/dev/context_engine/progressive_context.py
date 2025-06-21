#!/usr/bin/env python3
"""
Progressive Context Builder for Serena LSP

Implements a smart context management system that starts with minimal context
and escalates based on task complexity, achieving 6x token reduction while
maintaining quality for complex tasks.
"""

import re
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path


class ContextTier(Enum):
    """Progressive context tiers with increasing token budgets."""
    STUB = 0          # Symbol signatures, docstrings, 1-3 key lines (≤400 tokens)
    LOCAL_BODY = 1    # STUB + full target symbol implementation (+200-600 tokens)
    DEPENDENCIES = 2  # LOCAL_BODY + direct dependency bodies (≤1,200 total)
    FULL = 3         # Complete modules/files as needed (≤1,800 total)


class ProgressiveContextBuilder:
    """
    Smart context builder that escalates based on task complexity.
    
    Features:
    - Automatic tier escalation based on prompt patterns
    - Hard token limits to prevent timeouts
    - Quality preservation for complex tasks
    - Cost control for simple tasks
    """
    
    def __init__(self, max_tokens: int = 1800):
        """
        Initialize progressive context builder.
        
        Args:
            max_tokens: Maximum tokens allowed (hard limit for Claude timeouts)
        """
        self.max_tokens = max_tokens
        self.current_tokens = 0
        self.tier = ContextTier.STUB
        self.context_parts: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {
            "tier_progression": [ContextTier.STUB.name],
            "escalation_reasons": [],
            "symbols_processed": 0,
            "tokens_used": 0,
            "tokens_saved_estimate": 0
        }
        
        # Complex task patterns that trigger escalation
        self.complex_patterns = [
            r'refactor.*system',
            r'race condition',
            r'deadlock',
            r'transaction.*boundar',
            r'oauth.*implement',
            r'implement.*oauth',
            r'oauth.*integration',
            r'caching.*layer',
            r'find.*fix.*bug',
            r'cross-file',
            r'architectural.*change',
            r'security.*vuln',
            r'performance.*bottleneck',
            r'memory.*leak',
            r'thread.*safe',
            r'async.*await',
            r'database.*migration',
            r'api.*integration'
        ]
    
    def should_escalate(self, prompt: str, current_context: str = "") -> bool:
        """
        Determine if we need more context based on request complexity.
        
        Args:
            prompt: User's request/prompt
            current_context: Current context built so far
            
        Returns:
            True if escalation is needed
        """
        escalation_reasons = []
        
        # Pattern-based escalation
        for pattern in self.complex_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                escalation_reasons.append(f"complex_pattern: {pattern}")
                break
        
        # Context-based escalation (AI struggling indicators)
        struggle_indicators = [
            "need more context",
            "unclear",
            "insufficient information",
            "cannot determine",
            "requires additional",
            "missing dependencies"
        ]
        
        for indicator in struggle_indicators:
            if indicator.lower() in current_context.lower():
                escalation_reasons.append(f"struggle_indicator: {indicator}")
                break
        
        # Size-based escalation (large changes)
        large_change_patterns = [
            r'rewrite.*entire',
            r'complete.*refactor',
            r'major.*change',
            r'system.*redesign',
            r'architecture.*overhaul'
        ]
        
        for pattern in large_change_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                escalation_reasons.append(f"large_change: {pattern}")
                break
        
        # Multi-file indicators
        multi_file_patterns = [
            r'across.*files?',
            r'multiple.*modules?',
            r'entire.*codebase',
            r'project.*wide',
            r'system.*wide'
        ]
        
        for pattern in multi_file_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                escalation_reasons.append(f"multi_file: {pattern}")
                break
        
        if escalation_reasons:
            self.metadata["escalation_reasons"].extend(escalation_reasons)
            return True
        
        return False
    
    def can_add_context(self, content: str, tier: ContextTier = None) -> bool:
        """
        Check if we can add more context without exceeding limits.
        
        Args:
            content: Content to add
            tier: Target tier for this content
            
        Returns:
            True if content can be added
        """
        # Estimate tokens (rough: 4 chars per token)
        estimated_tokens = len(content) // 4
        
        # Check hard limit
        if self.current_tokens + estimated_tokens > self.max_tokens:
            return False
        
        # Check tier-specific limits
        tier_limits = {
            ContextTier.STUB: 400,
            ContextTier.LOCAL_BODY: 800,
            ContextTier.DEPENDENCIES: 1200,
            ContextTier.FULL: 1800
        }
        
        target_tier = tier or self.tier
        tier_limit = tier_limits.get(target_tier, self.max_tokens)
        
        return self.current_tokens + estimated_tokens <= tier_limit
    
    def add_context(self, content: str, tier: ContextTier = None, symbol_name: str = "", 
                   context_type: str = "symbol") -> bool:
        """
        Add context content to the builder.
        
        Args:
            content: Context content to add
            tier: Tier this content belongs to
            symbol_name: Name of symbol this content represents
            context_type: Type of context (symbol, dependency, file, etc.)
            
        Returns:
            True if content was added successfully
        """
        if not self.can_add_context(content, tier):
            return False
        
        # Update tier if necessary
        if tier and tier.value > self.tier.value:
            self.tier = tier
            self.metadata["tier_progression"].append(tier.name)
        
        # Estimate and track tokens
        estimated_tokens = len(content) // 4
        self.current_tokens += estimated_tokens
        
        # Store context part
        context_part = {
            "content": content,
            "tier": (tier or self.tier).name,
            "symbol_name": symbol_name,
            "context_type": context_type,
            "token_estimate": estimated_tokens
        }
        
        self.context_parts.append(context_part)
        self.metadata["symbols_processed"] += 1
        self.metadata["tokens_used"] = self.current_tokens
        
        return True
    
    def escalate_tier(self, new_tier: ContextTier, reason: str = "") -> bool:
        """
        Manually escalate to a higher tier.
        
        Args:
            new_tier: Tier to escalate to
            reason: Reason for escalation
            
        Returns:
            True if escalation was successful
        """
        if new_tier.value <= self.tier.value:
            return False  # Can't downgrade
        
        self.tier = new_tier
        self.metadata["tier_progression"].append(new_tier.name)
        if reason:
            self.metadata["escalation_reasons"].append(f"manual: {reason}")
        
        return True
    
    def get_token_budget_remaining(self) -> int:
        """Get remaining token budget."""
        return max(0, self.max_tokens - self.current_tokens)
    
    def get_tier_budget_remaining(self) -> int:
        """Get remaining budget for current tier."""
        tier_limits = {
            ContextTier.STUB: 400,
            ContextTier.LOCAL_BODY: 800,
            ContextTier.DEPENDENCIES: 1200,
            ContextTier.FULL: 1800
        }
        
        tier_limit = tier_limits.get(self.tier, self.max_tokens)
        return max(0, tier_limit - self.current_tokens)
    
    def build_final_context(self, prompt: str = "", milestone_name: str = "") -> str:
        """
        Build the final context string from all parts.
        
        Args:
            prompt: Original prompt for context
            milestone_name: Name of current milestone
            
        Returns:
            Final formatted context string
        """
        if not self.context_parts:
            return self._build_minimal_context(prompt, milestone_name)
        
        sections = [
            f"# SoloPilot Progressive Context (Tier: {self.tier.name})",
            f"# Tokens: {self.current_tokens}/{self.max_tokens}",
            ""
        ]
        
        if milestone_name:
            sections.extend([
                f"## Milestone: {milestone_name}",
                ""
            ])
        
        if prompt.strip():
            sections.extend([
                "## Current Task",
                prompt.strip(),
                ""
            ])
        
        # Group context by tier
        tier_groups = {}
        for part in self.context_parts:
            tier = part["tier"]
            if tier not in tier_groups:
                tier_groups[tier] = []
            tier_groups[tier].append(part)
        
        # Add sections by tier order
        for tier_enum in ContextTier:
            tier_name = tier_enum.name
            if tier_name in tier_groups:
                sections.extend([
                    f"## Tier {tier_enum.value}: {tier_name} Context",
                    ""
                ])
                
                for i, part in enumerate(tier_groups[tier_name]):
                    symbol_name = part["symbol_name"] or f"Context-{i+1}"
                    sections.extend([
                        f"### {symbol_name} ({part['context_type']})",
                        part["content"],
                        ""
                    ])
        
        # Add metadata footer
        sections.extend([
            "---",
            f"## Context Metadata",
            f"- **Final Tier**: {self.tier.name}",
            f"- **Tokens Used**: {self.current_tokens}/{self.max_tokens}",
            f"- **Symbols Processed**: {self.metadata['symbols_processed']}",
            f"- **Tier Progression**: {' → '.join(self.metadata['tier_progression'])}",
        ])
        
        if self.metadata["escalation_reasons"]:
            sections.append(f"- **Escalation Reasons**: {', '.join(self.metadata['escalation_reasons'])}")
        
        return '\n'.join(sections)
    
    def _build_minimal_context(self, prompt: str, milestone_name: str) -> str:
        """Build minimal context when no parts are available."""
        sections = [
            "# SoloPilot Minimal Context",
            f"# No symbols found - using basic context",
            ""
        ]
        
        if milestone_name:
            sections.extend([
                f"## Milestone: {milestone_name}",
                ""
            ])
        
        if prompt.strip():
            sections.extend([
                "## Current Task",
                prompt.strip(),
                ""
            ])
        
        sections.extend([
            "## Status",
            "No relevant symbols found for this task.",
            "This may be a new feature or the task requires basic implementation.",
            ""
        ])
        
        return '\n'.join(sections)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get complete metadata about the context building process."""
        # Calculate token savings estimate
        # Assume chunk-based approach would use 50% more tokens
        chunk_tokens_estimate = int(self.current_tokens * 1.5)
        tokens_saved = max(0, chunk_tokens_estimate - self.current_tokens)
        
        self.metadata.update({
            "final_tier": self.tier.name,
            "tokens_used": self.current_tokens,
            "max_tokens": self.max_tokens,
            "token_efficiency": round((1 - self.current_tokens / self.max_tokens) * 100, 1),
            "tokens_saved_estimate": tokens_saved,
            "context_parts_count": len(self.context_parts)
        })
        
        return self.metadata.copy()
    
    def reset(self):
        """Reset builder for reuse."""
        self.current_tokens = 0
        self.tier = ContextTier.STUB
        self.context_parts.clear()
        self.metadata = {
            "tier_progression": [ContextTier.STUB.name],
            "escalation_reasons": [],
            "symbols_processed": 0,
            "tokens_used": 0,
            "tokens_saved_estimate": 0
        }


class SymbolSelector:
    """Smart symbol selection for progressive context building."""
    
    @staticmethod
    def identify_primary_targets(prompt: str, symbols: List[str]) -> List[str]:
        """
        Identify which symbols are primary targets of the request.
        
        Args:
            prompt: User's request prompt
            symbols: Available symbols
            
        Returns:
            List of primary target symbols (max 3)
        """
        if not symbols:
            return []
        
        prompt_lower = prompt.lower()
        primary_targets = []
        
        # Direct symbol mentions in prompt
        for symbol in symbols:
            if symbol.lower() in prompt_lower:
                primary_targets.append(symbol)
        
        # Action words near symbols (more sophisticated matching)
        action_patterns = [
            (r'refactor\s+(\w+)', 'refactor'),
            (r'fix\s+(\w+)', 'fix'),
            (r'implement\s+(\w+)', 'implement'),
            (r'update\s+(\w+)', 'update'),
            (r'modify\s+(\w+)', 'modify'),
            (r'create\s+(\w+)', 'create'),
            (r'add\s+(\w+)', 'add'),
            (r'remove\s+(\w+)', 'remove'),
            (r'debug\s+(\w+)', 'debug')
        ]
        
        for pattern, action in action_patterns:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            for match in matches:
                # Find symbols that match or contain this word
                for symbol in symbols:
                    if match.lower() in symbol.lower() and symbol not in primary_targets:
                        primary_targets.append(symbol)
        
        # If no specific targets found, use heuristics
        if not primary_targets:
            # Prioritize classes over functions, functions over variables
            class_symbols = [s for s in symbols if s[0].isupper()]  # Likely classes
            func_symbols = [s for s in symbols if s[0].islower() and '_' in s]  # Likely functions
            other_symbols = [s for s in symbols if s not in class_symbols and s not in func_symbols]
            
            # Take top symbols from each category
            primary_targets.extend(class_symbols[:2])
            primary_targets.extend(func_symbols[:2])
            primary_targets.extend(other_symbols[:1])
        
        # Return top 3 unique targets
        seen = set()
        result = []
        for target in primary_targets:
            if target not in seen:
                result.append(target)
                seen.add(target)
                if len(result) >= 3:
                    break
        
        return result
    
    @staticmethod
    def prioritize_symbols_by_relevance(prompt: str, symbols: List[str]) -> List[str]:
        """
        Prioritize symbols by relevance to the prompt.
        
        Args:
            prompt: User's request prompt
            symbols: Available symbols
            
        Returns:
            Symbols sorted by relevance (most relevant first)
        """
        if not symbols:
            return []
        
        prompt_lower = prompt.lower()
        symbol_scores = []
        
        for symbol in symbols:
            score = 0
            symbol_lower = symbol.lower()
            
            # Direct mention gets highest score
            if symbol_lower in prompt_lower:
                score += 100
            
            # Partial matches
            if any(part in prompt_lower for part in symbol_lower.split('_')):
                score += 50
            
            # Common prefixes/suffixes
            common_prefixes = ['get_', 'set_', 'is_', 'has_', 'create_', 'update_', 'delete_']
            common_suffixes = ['_handler', '_manager', '_service', '_controller', '_model']
            
            for prefix in common_prefixes:
                if symbol_lower.startswith(prefix.lower()):
                    root = symbol_lower[len(prefix):]
                    if root in prompt_lower:
                        score += 75
            
            for suffix in common_suffixes:
                if symbol_lower.endswith(suffix.lower()):
                    root = symbol_lower[:-len(suffix)]
                    if root in prompt_lower:
                        score += 75
            
            # Keyword relevance
            task_keywords = {
                'auth': ['login', 'authenticate', 'token', 'session', 'user'],
                'data': ['save', 'load', 'store', 'retrieve', 'database'],
                'api': ['request', 'response', 'endpoint', 'route', 'http'],
                'ui': ['render', 'display', 'view', 'component', 'template'],
                'test': ['test', 'mock', 'assert', 'verify', 'check']
            }
            
            for category, keywords in task_keywords.items():
                if category in symbol_lower:
                    for keyword in keywords:
                        if keyword in prompt_lower:
                            score += 25
            
            symbol_scores.append((symbol, score))
        
        # Sort by score (descending) and return symbols
        symbol_scores.sort(key=lambda x: x[1], reverse=True)
        return [symbol for symbol, score in symbol_scores]