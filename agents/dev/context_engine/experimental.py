#!/usr/bin/env python3
"""
LangChain + Chroma Context Engine for SoloPilot Dev Agent

Replaces the simple context_packer with a more sophisticated system using:
- LangChain PromptTemplate for structured prompts
- Chroma vector database for context storage and retrieval
- Token counting with 25k guard rails
- Persistent context storage across sessions
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

try:
    from langchain.prompts import PromptTemplate
    from langchain.schema import Document
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


class ContextEngine:
    """
    Advanced context engine using LangChain and Chroma for context management.
    """
    
    def __init__(self, persist_directory: Optional[str] = None, collection_name: str = "solopilot_context"):
        """
        Initialize the context engine.
        
        Args:
            persist_directory: Directory to persist Chroma database (default: temp)
            collection_name: Name of the Chroma collection
        """
        self.persist_directory = persist_directory or os.path.join(tempfile.gettempdir(), "solopilot_chroma")
        self.collection_name = collection_name
        self.max_tokens = 25000  # Token guard rail
        self.chroma_client = None
        self.collection = None
        self.text_splitter = None
        
        # Initialize components if available
        self._initialize_components()
        
    def _initialize_components(self):
        """Initialize LangChain and Chroma components if available."""
        if not LANGCHAIN_AVAILABLE:
            print("⚠️  LangChain not available. Context engine will use fallback mode.")
            return
            
        if not CHROMA_AVAILABLE:
            print("⚠️  ChromaDB not available. Context engine will use fallback mode.")
            return
            
        try:
            # Initialize Chroma client with persistence
            os.makedirs(self.persist_directory, exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "SoloPilot development context storage"}
            )
            
            # Initialize text splitter for chunking
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
            
            print(f"✅ Context engine initialized with Chroma at {self.persist_directory}")
            
        except Exception as e:
            print(f"⚠️  Failed to initialize context engine: {e}")
            self.chroma_client = None
            self.collection = None

    def build_enhanced_context(
        self, 
        milestone_path: Path, 
        prompt: str,
        include_similar: bool = True,
        similarity_threshold: float = 0.7
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build enhanced context using LangChain prompts and Chroma retrieval.
        
        Args:
            milestone_path: Path to milestone directory
            prompt: The main prompt/query
            include_similar: Whether to include similar context from Chroma
            similarity_threshold: Minimum similarity score for retrieval
            
        Returns:
            Tuple of (enhanced_prompt, context_metadata)
        """
        if not self._is_available():
            # Fallback to simple context building
            return self._build_fallback_context(milestone_path, prompt)
        
        try:
            # Collect context from milestone
            context_data = self._collect_milestone_context(milestone_path)
            
            # Store context in Chroma for future retrieval
            if context_data:
                self._store_context_in_chroma(milestone_path, context_data)
            
            # Retrieve similar context if requested
            similar_contexts = []
            if include_similar and prompt.strip():
                similar_contexts = self._retrieve_similar_context(prompt, similarity_threshold)
            
            # Build enhanced prompt using LangChain template
            enhanced_prompt = self._build_langchain_prompt(
                context_data, similar_contexts, prompt
            )
            
            # Check token limits
            token_count = self._estimate_token_count(enhanced_prompt)
            if token_count > self.max_tokens:
                enhanced_prompt = self._truncate_context(enhanced_prompt, self.max_tokens)
                token_count = self.max_tokens
            
            metadata = {
                "token_count": token_count,
                "milestone_path": str(milestone_path),
                "similar_contexts_found": len(similar_contexts),
                "context_sections": list(context_data.keys()) if context_data else [],
                "engine": "langchain_chroma"
            }
            
            return enhanced_prompt, metadata
            
        except Exception as e:
            print(f"⚠️  Context engine error: {e}")
            return self._build_fallback_context(milestone_path, prompt)

    def _collect_milestone_context(self, milestone_path: Path) -> Dict[str, str]:
        """
        Collect context data from milestone directory.
        
        Args:
            milestone_path: Path to milestone directory
            
        Returns:
            Dictionary of context sections
        """
        context_data = {}
        
        if not milestone_path.exists():
            return context_data
        
        # Load milestone JSON
        milestone_json = milestone_path / "milestone.json"
        if milestone_json.exists():
            try:
                with open(milestone_json, "r") as f:
                    milestone_data = json.load(f)
                context_data["milestone"] = json.dumps(milestone_data, indent=2)
            except (json.JSONDecodeError, IOError) as e:
                context_data["milestone"] = f"Error loading milestone.json: {e}"
        
        # Collect package manifests
        manifest_files = [
            "package.json", "requirements.txt", "Pipfile", "pyproject.toml",
            "pom.xml", "build.gradle", "Cargo.toml", "go.mod", "composer.json"
        ]
        
        manifests = []
        for manifest_name in manifest_files:
            manifest_path = milestone_path / manifest_name
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r") as f:
                        content = f.read().strip()
                    if content:
                        manifests.append(f"### {manifest_name}\n```\n{content}\n```")
                except IOError:
                    manifests.append(f"### {manifest_name}\n(Error reading file)")
        
        if manifests:
            context_data["manifests"] = "\n\n".join(manifests)
        
        # Collect README/documentation
        doc_files = ["README.md", "STRUCTURE.md", "PROJECT.md"]
        for doc_file in doc_files:
            doc_path = milestone_path / doc_file
            if doc_path.exists():
                try:
                    with open(doc_path, "r") as f:
                        content = f.read().strip()
                    if content and len(content) < 3000:  # Limit doc size
                        context_data["documentation"] = content
                        break
                except IOError:
                    continue
        
        return context_data

    def _store_context_in_chroma(self, milestone_path: Path, context_data: Dict[str, str]):
        """
        Store context data in Chroma for future retrieval.
        
        Args:
            milestone_path: Path to milestone directory
            context_data: Dictionary of context sections
        """
        if not self.collection:
            return
        
        try:
            # Create documents from context data
            documents = []
            metadatas = []
            ids = []
            
            milestone_id = str(milestone_path).replace("/", "_").replace("\\", "_")
            
            for section_name, content in context_data.items():
                if content and content.strip():
                    # Split large content into chunks
                    chunks = self.text_splitter.split_text(content)
                    
                    for i, chunk in enumerate(chunks):
                        doc_id = f"{milestone_id}_{section_name}_{i}"
                        documents.append(chunk)
                        metadatas.append({
                            "milestone_path": str(milestone_path),
                            "section": section_name,
                            "chunk_index": i,
                            "total_chunks": len(chunks)
                        })
                        ids.append(doc_id)
            
            if documents:
                # Add to collection (upsert to handle duplicates)
                self.collection.upsert(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                
        except Exception as e:
            print(f"⚠️  Failed to store context in Chroma: {e}")

    def _retrieve_similar_context(self, query: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Retrieve similar context from Chroma database.
        
        Args:
            query: Query string for similarity search
            threshold: Minimum similarity threshold
            
        Returns:
            List of similar context items
        """
        if not self.collection:
            return []
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=5,  # Top 5 similar contexts
                include=["documents", "metadatas", "distances"]
            )
            
            similar_contexts = []
            if results["documents"] and results["documents"][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0], 
                    results["distances"][0]
                )):
                    # Convert distance to similarity (lower distance = higher similarity)
                    similarity = 1.0 - distance
                    
                    if similarity >= threshold:
                        similar_contexts.append({
                            "content": doc,
                            "metadata": metadata,
                            "similarity": similarity
                        })
            
            return similar_contexts
            
        except Exception as e:
            print(f"⚠️  Failed to retrieve similar context: {e}")
            return []

    def _build_langchain_prompt(
        self, 
        context_data: Dict[str, str], 
        similar_contexts: List[Dict[str, Any]], 
        prompt: str
    ) -> str:
        """
        Build enhanced prompt using LangChain PromptTemplate.
        
        Args:
            context_data: Current milestone context
            similar_contexts: Similar contexts from Chroma
            prompt: Main prompt
            
        Returns:
            Enhanced prompt string
        """
        # Define the prompt template
        template = """## Development Context

{milestone_context}

{package_manifests}

{documentation}

{similar_contexts}

---

## Task Instructions

{main_prompt}

Please generate high-quality code that:
1. Follows the context and requirements above
2. Includes proper error handling and validation
3. Has comprehensive unit tests
4. Uses appropriate design patterns
5. Includes clear documentation and comments
"""
        
        prompt_template = PromptTemplate(
            input_variables=[
                "milestone_context", "package_manifests", "documentation", 
                "similar_contexts", "main_prompt"
            ],
            template=template
        )
        
        # Prepare context sections
        milestone_context = ""
        if "milestone" in context_data:
            milestone_context = f"### Milestone Information\n```json\n{context_data['milestone']}\n```\n"
        
        package_manifests = ""
        if "manifests" in context_data:
            package_manifests = f"### Package Dependencies\n{context_data['manifests']}\n"
        
        documentation = ""
        if "documentation" in context_data:
            documentation = f"### Project Documentation\n```markdown\n{context_data['documentation']}\n```\n"
        
        similar_contexts_text = ""
        if similar_contexts:
            similar_sections = []
            for ctx in similar_contexts[:3]:  # Limit to top 3
                similar_sections.append(
                    f"**Similar Context** (similarity: {ctx['similarity']:.2f})\n```\n{ctx['content']}\n```"
                )
            similar_contexts_text = f"### Related Context\n{chr(10).join(similar_sections)}\n"
        
        # Format the final prompt
        enhanced_prompt = prompt_template.format(
            milestone_context=milestone_context,
            package_manifests=package_manifests,
            documentation=documentation,
            similar_contexts=similar_contexts_text,
            main_prompt=prompt
        )
        
        return enhanced_prompt

    def _estimate_token_count(self, text: str) -> int:
        """
        Estimate token count using simple heuristic.
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        # Simple heuristic: ~4 characters per token for English text
        return len(text) // 4

    def _truncate_context(self, prompt: str, max_tokens: int) -> str:
        """
        Truncate context to fit within token limits.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum allowed tokens
            
        Returns:
            Truncated prompt
        """
        target_chars = max_tokens * 4  # Approximate character limit
        
        if len(prompt) <= target_chars:
            return prompt
        
        # Try to preserve the main prompt at the end
        lines = prompt.split('\n')
        
        # Find the main prompt section
        main_prompt_start = -1
        for i, line in enumerate(lines):
            if "## Task Instructions" in line:
                main_prompt_start = i
                break
        
        if main_prompt_start > 0:
            # Preserve main prompt, truncate context
            main_prompt_section = '\n'.join(lines[main_prompt_start:])
            available_chars = target_chars - len(main_prompt_section)
            
            if available_chars > 0:
                context_section = '\n'.join(lines[:main_prompt_start])
                truncated_context = context_section[:available_chars]
                return truncated_context + "\n\n[CONTEXT TRUNCATED DUE TO TOKEN LIMIT]\n\n" + main_prompt_section
        
        # Fallback: simple truncation
        return prompt[:target_chars] + "\n\n[TRUNCATED DUE TO TOKEN LIMIT]"

    def _build_fallback_context(self, milestone_path: Path, prompt: str) -> Tuple[str, Dict[str, Any]]:
        """
        Fallback context building when LangChain/Chroma are not available.
        
        Args:
            milestone_path: Path to milestone directory
            prompt: Main prompt
            
        Returns:
            Tuple of (simple_prompt, metadata)
        """
        # Import and use the original context_packer as fallback
        try:
            from agents.dev.context_packer import build_context
            context = build_context(milestone_path)
            
            enhanced_prompt = context + prompt if context.strip() else prompt
            
            metadata = {
                "token_count": len(enhanced_prompt) // 4,
                "milestone_path": str(milestone_path),
                "engine": "fallback_context_packer"
            }
            
            return enhanced_prompt, metadata
            
        except Exception as e:
            print(f"⚠️  Fallback context building failed: {e}")
            return prompt, {"engine": "none", "error": str(e)}

    def _is_available(self) -> bool:
        """Check if the context engine is fully available."""
        return (
            LANGCHAIN_AVAILABLE and 
            CHROMA_AVAILABLE and 
            self.chroma_client is not None and 
            self.collection is not None
        )

    def clear_context(self):
        """Clear all stored context from Chroma."""
        if self.collection:
            try:
                self.collection.delete()
                print("✅ Context cleared from Chroma database")
            except Exception as e:
                print(f"⚠️  Failed to clear context: {e}")

    def get_context_stats(self) -> Dict[str, Any]:
        """Get statistics about stored context."""
        if not self.collection:
            return {"available": False, "engine": "fallback"}
        
        try:
            count = self.collection.count()
            return {
                "available": True,
                "engine": "langchain_chroma",
                "total_documents": count,
                "persist_directory": self.persist_directory,
                "collection_name": self.collection_name,
                "max_tokens": self.max_tokens
            }
        except Exception as e:
            return {"available": False, "error": str(e)}


# Convenience function for backward compatibility
def build_enhanced_context(milestone_path: Path, prompt: str = "") -> str:
    """
    Build enhanced context using the new context engine.
    
    Args:
        milestone_path: Path to milestone directory
        prompt: Optional prompt for similarity matching
        
    Returns:
        Enhanced context string
    """
    engine = ContextEngine()
    enhanced_prompt, _ = engine.build_enhanced_context(milestone_path, prompt)
    return enhanced_prompt