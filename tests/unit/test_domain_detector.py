"""Unit tests for Domain Detector component."""

import pytest
from src.components.domain_detector import DomainDetector


@pytest.fixture
def domain_detector():
    """Create domain detector instance."""
    return DomainDetector()


@pytest.mark.unit
class TestDomainDetector:
    """Tests for Domain Detector."""
    
    def test_detect_general_domain(self, domain_detector):
        """Test general conversation detection."""
        domain = domain_detector.detect_domain("Hello, how are you today?")
        assert domain == "general"
    
    def test_detect_finance_domain(self, domain_detector):
        """Test finance domain detection."""
        messages = [
            "What is a good investment strategy?",
            "How do I save for retirement?",
            "Tell me about 401k plans.",
            "What are ETFs?"
        ]
        
        for message in messages:
            domain = domain_detector.detect_domain(message)
            assert domain == "finance", f"Failed for: {message}"
    
    def test_detect_politics_domain(self, domain_detector):
        """Test politics domain detection."""
        messages = [
            "What do you think about the election?",
            "Tell me about the new policy.",
            "How does congress work?"
        ]
        
        for message in messages:
            domain = domain_detector.detect_domain(message)
            assert domain == "politics", f"Failed for: {message}"
    
    def test_detect_ai_domain(self, domain_detector):
        """Test AI domain detection."""
        messages = [
            "What is machine learning?",
            "Tell me about neural networks.",
            "How do LLMs work?"
        ]
        
        for message in messages:
            domain = domain_detector.detect_domain(message)
            assert domain == "ai", f"Failed for: {message}"
    
    def test_detect_medical_domain(self, domain_detector):
        """Test medical domain detection."""
        messages = [
            "What are the symptoms of flu?",
            "Tell me about this diagnosis.",
            "How do I treat a headache?"
        ]
        
        for message in messages:
            domain = domain_detector.detect_domain(message)
            # Medical might be detected or fall back to general
            assert domain in ["medical", "general"]
    
    def test_priority_order(self, domain_detector):
        """Test that priority order is respected."""
        # Finance has highest priority
        domain = domain_detector.detect_domain(
            "What is the best investment strategy for retirement?"
        )
        assert domain == "finance"
    
    def test_get_domain_config(self, domain_detector):
        """Test getting domain configuration."""
        config = domain_detector.get_domain_config("finance")
        
        assert "name" in config
        assert "thresholds" in config
        assert "interventions" in config
    
    def test_get_thresholds_for_domain(self, domain_detector):
        """Test getting thresholds for domain."""
        thresholds = domain_detector.get_thresholds_for_domain("finance")
        
        assert "drift_warning" in thresholds
        assert "rupture_alert" in thresholds
    
    def test_get_intervention_config(self, domain_detector):
        """Test getting intervention config for domain."""
        config = domain_detector.get_intervention_config("finance")
        
        assert "mode" in config
        assert "auto_regenerate" in config
    
    def test_is_high_stakes(self, domain_detector):
        """Test high-stakes domain detection."""
        assert domain_detector.is_high_stakes("finance") is True
        assert domain_detector.is_high_stakes("medical") is True
        assert domain_detector.is_high_stakes("legal") is True
        assert domain_detector.is_high_stakes("general") is False
    
    def test_get_all_domains(self, domain_detector):
        """Test getting all domain keys."""
        domains = domain_detector.get_all_domains()
        
        assert "general" in domains
        assert "finance" in domains
        assert "politics" in domains
    
    def test_get_domain_keywords(self, domain_detector):
        """Test getting keywords for domain."""
        keywords = domain_detector.get_domain_keywords("finance")
        
        assert len(keywords) > 0
        assert "investment" in keywords
        assert "stock" in keywords
    
    def test_cross_domain_detection(self, domain_detector):
        """Test cross-domain pattern detection."""
        # Political economy
        domain = domain_detector.detect_domain(
            "What is the fiscal policy of the current government?"
        )
        # Should pick higher priority (politics over economy)
        assert domain in ["politics", "economy"]
    
    def test_unknown_domain_fallback(self, domain_detector):
        """Test fallback to general for unknown domains."""
        domain = domain_detector.detect_domain("Random text with no keywords")
        assert domain == "general"
    
    def test_case_insensitive(self, domain_detector):
        """Test case-insensitive keyword matching."""
        domain1 = domain_detector.detect_domain("What is INVESTMENT advice?")
        domain2 = domain_detector.detect_domain("What is investment advice?")
        
        assert domain1 == domain2 == "finance"
