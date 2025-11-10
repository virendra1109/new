"""Agent Indexer for semantic agent selection using FAISS."""
import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict

from .embeddings import get_embedding


class AgentIndexer:
    """FAISS-based indexer for semantic agent selection."""
    CACHE_DIR = Path("cache/faiss_indexes")
    
    def __init__(self, agents_info: Dict[str, str]) -> None:
        """
        Initialize agent indexer with agent metadata.
        
        Args:
            agents_info: Dict mapping agent_name -> description
        """
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.agents = list(agents_info.keys())
        self.descriptions = list(agents_info.values())
        
        index_path = self.CACHE_DIR / "agent_index.faiss"
        metadata_path = self.CACHE_DIR / "agent_index.pkl"
        
        # Load or build index
        if index_path.exists() and metadata_path.exists():
            with open(metadata_path, 'rb') as f:
                cached = pickle.load(f)
            
            if cached == list(agents_info.items()):
                self.index = faiss.read_index(str(index_path))
                print(f"Agent index loaded from cache ({len(self.agents)} agents)")
            else:
                print("Agent metadata changed, rebuilding index...")
                self._build_and_save(index_path, metadata_path, agents_info)
        else:
            self._build_and_save(index_path, metadata_path, agents_info)
    
    def _build_and_save(self, index_path: Path, metadata_path: Path, agents_info: Dict) -> None:
        """Build FAISS index and save to disk."""
        embeddings = np.array([
            get_embedding(f"{name}: {desc}") 
            for name, desc in agents_info.items()
        ], dtype=np.float32)
        
        self.index = faiss.IndexFlatL2(embeddings.shape[1])
        self.index.add(embeddings)
        
        faiss.write_index(self.index, str(index_path))
        with open(metadata_path, 'wb') as f:
            pickle.dump(list(agents_info.items()), f)
        
        print(f"Agent index built and cached ({len(self.agents)} agents)")
    
    def search(self, query: str, top_k: int = 3) -> List[str]:
        """
        Search for relevant agents based on query.
        
        Args:
            query: User query
            top_k: Number of agents to return
            
        Returns:
            List of agent names
        """
        query_emb = get_embedding(query).reshape(1, -1)
        _, indices = self.index.search(query_emb, min(top_k, len(self.agents)))
        
        selected = [self.agents[idx] for idx in indices[0]]
        print(f"Agent selection: {', '.join(selected)} (from {len(self.agents)} total)")
        return selected