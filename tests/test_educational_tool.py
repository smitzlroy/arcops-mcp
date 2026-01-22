"""
Tests for ArcOps Educational Tool.
"""

import pytest

from server.tools.educational_tool import ArcOpsEducationalTool


class TestArcOpsEducationalTool:
    """Test suite for ArcOpsEducationalTool."""

    @pytest.fixture
    def tool(self) -> ArcOpsEducationalTool:
        """Create a tool instance for testing."""
        return ArcOpsEducationalTool()

    def test_tool_metadata(self, tool: ArcOpsEducationalTool) -> None:
        """Test tool has correct metadata."""
        assert tool.name == "arcops.explain"
        assert "educational" in tool.description.lower() or "content" in tool.description.lower()
        assert tool.input_schema["type"] == "object"
        assert "topic" in tool.input_schema["properties"]

    def test_input_schema_has_all_topics(self, tool: ArcOpsEducationalTool) -> None:
        """Test that input schema includes all available topics."""
        topic_schema = tool.input_schema["properties"]["topic"]
        assert "enum" in topic_schema

        # Should include all TOPICS plus 'list'
        expected_topics = list(tool.TOPICS.keys()) + ["list"]
        for topic in expected_topics:
            assert topic in topic_schema["enum"]

    async def test_list_topics(self, tool: ArcOpsEducationalTool) -> None:
        """Test listing all available topics."""
        result = await tool.execute({"topic": "list"})

        assert result["success"] is True
        assert result["type"] == "topic_list"
        assert "topics" in result
        assert len(result["topics"]) == len(tool.TOPICS)

        # Check each topic has required fields
        for topic in result["topics"]:
            assert "id" in topic
            assert "title" in topic
            assert "description" in topic

    async def test_get_connectivity_topic(self, tool: ArcOpsEducationalTool) -> None:
        """Test getting the connectivity topic."""
        result = await tool.execute({"topic": "connectivity"})

        assert result["success"] is True
        assert result["type"] == "educational_content"
        assert result["topic"] == "connectivity"
        assert "title" in result
        assert "content" in result
        assert "links" in result
        assert len(result["links"]) > 0

    async def test_get_cluster_validation_topic(self, tool: ArcOpsEducationalTool) -> None:
        """Test getting the cluster_validation topic."""
        result = await tool.execute({"topic": "cluster_validation"})

        assert result["success"] is True
        assert result["topic"] == "cluster_validation"
        assert "AKS Arc" in result["content"]

    async def test_get_known_issues_topic(self, tool: ArcOpsEducationalTool) -> None:
        """Test getting the known_issues topic."""
        result = await tool.execute({"topic": "known_issues"})

        assert result["success"] is True
        assert result["topic"] == "known_issues"
        assert "Support.AksArc" in result["content"]

    async def test_get_tsg_search_topic(self, tool: ArcOpsEducationalTool) -> None:
        """Test getting the tsg_search topic."""
        result = await tool.execute({"topic": "tsg_search"})

        assert result["success"] is True
        assert result["topic"] == "tsg_search"
        assert "TSG" in result["content"]

    async def test_get_logs_collection_topic(self, tool: ArcOpsEducationalTool) -> None:
        """Test getting the logs_collection topic."""
        result = await tool.execute({"topic": "logs_collection"})

        assert result["success"] is True
        assert result["topic"] == "logs_collection"
        assert "log" in result["content"].lower()

    async def test_get_learning_path_topic(self, tool: ArcOpsEducationalTool) -> None:
        """Test getting the learning_path topic."""
        result = await tool.execute({"topic": "learning_path"})

        assert result["success"] is True
        assert result["topic"] == "learning_path"
        assert "Beginner" in result["content"]
        assert "Intermediate" in result["content"]
        assert "Advanced" in result["content"]

    async def test_unknown_topic_returns_error(self, tool: ArcOpsEducationalTool) -> None:
        """Test that unknown topic returns an error."""
        result = await tool.execute({"topic": "unknown_topic"})

        assert result["success"] is False
        assert "error" in result
        assert "unknown_topic" in result["error"].lower()

    async def test_content_has_related_topics(self, tool: ArcOpsEducationalTool) -> None:
        """Test that educational content includes related topics."""
        result = await tool.execute({"topic": "connectivity"})

        assert result["success"] is True
        assert "related_topics" in result
        assert "connectivity" not in result["related_topics"]  # Current topic excluded
        assert len(result["related_topics"]) <= 3  # Max 3 related

    async def test_links_have_required_fields(self, tool: ArcOpsEducationalTool) -> None:
        """Test that links have title and url fields."""
        result = await tool.execute({"topic": "connectivity"})

        assert result["success"] is True
        for link in result["links"]:
            assert "title" in link
            assert "url" in link
            assert link["url"].startswith("https://")

    async def test_all_topics_have_content(self, tool: ArcOpsEducationalTool) -> None:
        """Test that all topics return valid content."""
        for topic_id in tool.TOPICS.keys():
            result = await tool.execute({"topic": topic_id})

            assert result["success"] is True, f"Topic {topic_id} failed"
            assert result["type"] == "educational_content"
            assert len(result["content"]) > 100  # Content should be substantial

    async def test_default_topic_is_list(self, tool: ArcOpsEducationalTool) -> None:
        """Test that default behavior is to list topics."""
        result = await tool.execute({})

        assert result["success"] is True
        assert result["type"] == "topic_list"
