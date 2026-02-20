"""
PedalBot API Client

Handles all communication with the FastAPI backend.
"""

import httpx
from typing import Optional, Dict, Any, List, Generator
from dataclasses import dataclass
import os
import json


# API Configuration
# Priority: Streamlit secrets > Environment variable > localhost
def get_api_url():
    """Get API URL from Streamlit secrets or environment."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'PEDALBOT_API_URL' in st.secrets:
            return st.secrets['PEDALBOT_API_URL']
    except:
        pass
    return os.getenv("PEDALBOT_API_URL", "http://localhost:8000")

API_BASE_URL = get_api_url()


@dataclass
class QueryResponse:
    """Response from PedalBot query."""
    answer: str
    conversation_id: str
    user_id: str
    pedal_name: str
    intent: Optional[str]
    confidence: float
    agent_path: List[str]
    hallucination_flag: bool
    fallback_reason: Optional[str]  # Why the query fell back (if it did)
    latency_ms: int
    cost_usd: float
    sources: Optional[List[str]] = None


@dataclass
class PedalInfo:
    """Information about an available pedal."""
    pedal_name: str
    manufacturer: Optional[str]
    pinecone_namespace: str
    chunk_count: int


class PedalBotClient:
    """Client for PedalBot FastAPI backend."""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(60.0, connect=10.0)
    
    def health_check(self) -> bool:
        """Check if the API is healthy."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
    
    def get_available_pedals(self) -> List[PedalInfo]:
        """Get list of available pedals."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}/api/query/pedals")
                response.raise_for_status()
                data = response.json()
                
                return [
                    PedalInfo(
                        pedal_name=p["pedal_name"],
                        manufacturer=p.get("manufacturer"),
                        pinecone_namespace=p["pinecone_namespace"],
                        chunk_count=p["chunk_count"]
                    )
                    for p in data.get("pedals", [])
                ]
        except Exception as e:
            print(f"Error fetching pedals: {e}")
            return []
    
    def query(
        self,
        query: str,
        pedal_name: str,
        conversation_id: Optional[str] = None
    ) -> QueryResponse:
        """Send a query to PedalBot."""
        payload = {
            "query": query,
            "pedal_name": pedal_name,
            "stream": False
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/query/",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            return QueryResponse(
                answer=data["answer"],
                conversation_id=data["conversation_id"],
                user_id=data["user_id"],
                pedal_name=data["pedal_name"],
                intent=data.get("intent"),
                confidence=data["confidence"],
                agent_path=data["agent_path"],
                hallucination_flag=data["hallucination_flag"],
                fallback_reason=data.get("fallback_reason"),
                latency_ms=data["latency_ms"],
                cost_usd=data["cost_usd"],
                sources=data.get("sources")
            )
    
    def upload_manual(self, pdf_file) -> Optional[Dict[str, Any]]:
        """
        Upload a PDF manual for indexing.
        
        Args:
            pdf_file: Streamlit UploadedFile object
            
        Returns:
            Response dict with manual_id, status, etc.
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                # Reset file position
                pdf_file.seek(0)
                
                files = {
                    "pdf_file": (pdf_file.name, pdf_file.read(), "application/pdf")
                }
                
                response = client.post(
                    f"{self.base_url}/api/ingest/upload",
                    files=files
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            # Try to extract error message
            try:
                error_data = e.response.json()
                raise Exception(error_data.get("detail", str(e)))
            except:
                raise Exception(f"Upload failed: {e.response.status_code}")
        except Exception as e:
            raise Exception(f"Upload failed: {str(e)}")
    
    def get_manuals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all uploaded manuals.
        
        Args:
            status: Optional filter by status (pending, processing, completed, failed)
            
        Returns:
            List of manual dictionaries
        """
        try:
            params = {}
            if status:
                params["status"] = status
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.base_url}/api/ingest/manuals",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                return data.get("manuals", [])
                
        except Exception as e:
            print(f"Error fetching manuals: {e}")
            return []
    
    def get_ingestion_status(self, manual_id: str) -> Optional[Dict[str, Any]]:
        """Get the processing status of a manual."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.base_url}/api/ingest/status/{manual_id}"
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Error fetching status: {e}")
            return None

    def retry_ingestion(self, manual_id: str) -> Optional[Dict[str, Any]]:
        """Retry ingestion for a failed manual."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/ingest/retry/{manual_id}"
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Error retrying ingestion: {e}")
            raise Exception(f"Retry failed: {str(e)}")
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation history by ID."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.base_url}/api/query/conversations/{conversation_id}"
                )
                
                if response.status_code == 404:
                    return None
                    
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Error fetching conversation: {e}")
            return None


# Singleton instance
_client: Optional[PedalBotClient] = None


def get_client() -> PedalBotClient:
    """Get or create API client singleton."""
    global _client
    if _client is None:
        _client = PedalBotClient()
    return _client
