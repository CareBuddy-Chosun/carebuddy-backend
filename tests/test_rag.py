from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
class TestRAGRetriever:
    async def test_retrieve_returns_empty_when_no_index(self):
        from app.rag.retriever import retrieve_user_context

        result = await retrieve_user_context("user-1", "headache")
        assert result == ""


@pytest.mark.asyncio
class TestEmbeddingService:
    @patch("app.services.embedding_service.index_session_summary", new_callable=AsyncMock)
    async def test_generate_session_embedding_no_session(self, mock_index):
        """If session doesn't exist, should return without error."""
        import uuid

        from app.services.embedding_service import generate_session_embedding

        with patch("app.services.embedding_service.AsyncSessionLocal") as mock_session_cls:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None

            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(return_value=mock_result)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_ctx

            await generate_session_embedding(uuid.uuid4())
            mock_index.assert_not_called()
