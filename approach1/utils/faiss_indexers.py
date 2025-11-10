"""FAISS Indexers with Keyword Matching"""
import faiss
import numpy as np
import pickle
from pathlib import Path
from .embeddings import get_embedding


class BaseFAISSIndexer:
    """Base class for FAISS indexing with caching"""
    CACHE_DIR = Path("cache/faiss_indexes")
    
    def __init__(self):
        self.index = None
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_or_build(self, index_path, metadata_path, current_data, build_fn, name):
        if index_path.exists() and metadata_path.exists():
            self.index = faiss.read_index(str(index_path))
            with open(metadata_path, 'rb') as f:
                cached = pickle.load(f)
            
            if cached != current_data:
                print(f"{name} changed, rebuilding...")
                build_fn()
                self._save(index_path, metadata_path, current_data)
            else:
                print(f"{name} loaded from cache")
        else:
            build_fn()
            self._save(index_path, metadata_path, current_data)
    
    def _save(self, index_path, metadata_path, data):
        faiss.write_index(self.index, str(index_path))
        with open(metadata_path, 'wb') as f:
            pickle.dump(data, f)


class FAISSToolIndexer(BaseFAISSIndexer):
    """Index tools with hybrid keyword + semantic search"""
    def __init__(self, server_name: str, tools: list):
        super().__init__()
        self.server_name = server_name
        self.tools = tools
        
        if not tools:
            return
        
        tool_info = [(t['name'], t['description']) for t in tools]
        self._load_or_build(
            self.CACHE_DIR / f"tool_{server_name}.faiss",
            self.CACHE_DIR / f"tool_{server_name}.pkl",
            tool_info,
            self._build_index,
            f"{server_name} tools ({len(tools)})"
        )
    
    def _build_index(self):
        embeddings = np.array([
            get_embedding(f"{t['name']}: {t['description']}")
            for t in self.tools
        ], dtype=np.float32)
        
        self.index = faiss.IndexFlatL2(embeddings.shape[1])
        self.index.add(embeddings)
    
    def search(self, query: str, top_k: int = 3) -> list:
        if not self.tools:
            return []
        
        query_lower = query.lower()
        keywords = query_lower.split()
        
        # Score each tool by keyword matches
        scored_tools = []
        for tool in self.tools:
            name_lower = tool['name'].lower()
            desc_lower = tool['description'].lower()
            
            # Count keyword matches
            score = sum(1 for kw in keywords if kw in name_lower or kw in desc_lower)
            scored_tools.append((score, tool))
        
        # Get tools with keyword matches
        keyword_matches = [t for s, t in scored_tools if s > 0]
        
        # If we have enough keyword matches, return those
        if len(keyword_matches) >= top_k:
            return sorted(keyword_matches, key=lambda t: sum(
                1 for kw in keywords if kw in t['name'].lower() or kw in t['description'].lower()
            ), reverse=True)[:top_k]
        
        # Otherwise combine keyword matches + semantic search
        query_emb = get_embedding(query).reshape(1, -1)
        _, indices = self.index.search(query_emb, min(top_k * 2, len(self.tools)))
        semantic_results = [self.tools[idx] for idx in indices[0]]
        
        # Merge: prioritize keyword matches, then add semantic
        result = keyword_matches.copy()
        for tool in semantic_results:
            if tool not in result and len(result) < top_k:
                result.append(tool)
        
        return result[:top_k]