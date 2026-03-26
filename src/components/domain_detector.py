"""Domain Detector component - Auto-detect conversation domains from keywords."""

import re
import yaml
import logging
from typing import Dict, List, Set, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class DomainDetector:
    """
    Domain Detector
    
    Responsibilities:
    - Load domain configurations from domains.yml
    - Detect domain from message keywords
    - Handle domain conflicts and priorities
    """
    
    DEFAULT_DOMAINS_PATH = "./config/domains.yml"
    
    def __init__(self, domains_path: str = ""):
        """
        Initialize domain detector.
        
        Args:
            domains_path: Path to domains.yml. Uses default if not provided.
        """
        self.domains_path = domains_path or self.DEFAULT_DOMAINS_PATH
        self.domains: Dict[str, Dict] = {}
        self.priority_order: List[str] = []
        self.selection_rules: Dict = {}
        self.cross_domain_patterns: List[Dict] = []
        
        self._load_domains()
    
    def _load_domains(self) -> None:
        """Load domain configuration from YAML file."""
        try:
            path = Path(self.domains_path).expanduser()
            
            # Try multiple locations
            if not path.exists():
                possible_paths = [
                    Path("./config/domains.yml"),
                    Path("~/.openclaw/brain-guard/domains.yml"),
                    Path(__file__).parent.parent.parent / "config" / "domains.yml"
                ]
                for p in possible_paths:
                    expanded = p.expanduser()
                    if expanded.exists():
                        path = expanded
                        break
            
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            
            self.domains = config.get('domains', {})
            self.selection_rules = config.get('selection_rules', {})
            self.priority_order = self.selection_rules.get('priority_order', [])
            self.cross_domain_patterns = config.get('cross_domain_patterns', [])
            
            # Compile keyword patterns
            for domain_key, domain_config in self.domains.items():
                keywords = domain_config.get('high_stakes_keywords', [])
                domain_config['_compiled_keywords'] = [
                    re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
                    for kw in keywords
                ]
            
            logger.info(f"Loaded {len(self.domains)} domains")
            
        except Exception as e:
            logger.error(f"Failed to load domains: {e}")
            # Fallback to basic domains
            self.domains = {"general": {"name": "General", "high_stakes_keywords": []}}
            self.priority_order = ["general"]
    
    def detect_domain(self, message: str) -> str:
        """
        Detect the domain of a message.
        
        Args:
            message: User message
            
        Returns:
            Domain key (e.g., "finance", "medical", "general")
        """
        message_lower = message.lower()
        
        # Score each domain
        domain_scores: Dict[str, float] = {}
        
        for domain_key, domain_config in self.domains.items():
            score = self._score_domain(message_lower, domain_config)
            if score > 0:
                domain_scores[domain_key] = score
        
        # No domain matched
        if not domain_scores:
            return "general"
        
        # Check for cross-domain patterns
        cross_domain = self._detect_cross_domain(message_lower)
        if cross_domain:
            # Return the higher priority domain
            domains_in_pattern = cross_domain.get('domains', [])
            for priority_domain in self.priority_order:
                if priority_domain in domains_in_pattern:
                    return priority_domain
        
        # Apply priority order for conflicts
        for priority_domain in self.priority_order:
            if priority_domain in domain_scores:
                return priority_domain
        
        # Return highest scoring domain
        return max(domain_scores, key=domain_scores.get)
    
    def _score_domain(self, message: str, domain_config: Dict) -> float:
        """
        Score how well a message matches a domain.
        
        Args:
            message: Lowercase message
            domain_config: Domain configuration
            
        Returns:
            Match score (0 = no match)
        """
        compiled_keywords = domain_config.get('_compiled_keywords', [])
        keywords = domain_config.get('high_stakes_keywords', [])
        
        if not compiled_keywords or not keywords:
            return 0.0
        
        matches = 0
        for pattern in compiled_keywords:
            if pattern.search(message):
                matches += 1
        
        # Also do simple substring matching for better coverage
        # But only count if keyword is at least 5 chars to avoid false positives
        for keyword in keywords:
            if len(keyword) >= 5 and keyword.lower() in message:
                matches += 0.5  # Half credit for substring match
        
        # Score based on match ratio
        if matches == 0:
            return 0.0
        
        # More matches = higher score, but with diminishing returns
        score = min(1.0, matches / 3)  # Cap at 3 matches
        
        return score
    
    def _detect_cross_domain(self, message: str) -> Dict:
        """
        Detect if message matches cross-domain patterns.
        
        Args:
            message: Lowercase message
            
        Returns:
            Cross-domain pattern dict or empty dict
        """
        for pattern in self.cross_domain_patterns:
            keywords = pattern.get('keywords', [])
            for keyword in keywords:
                if keyword.lower() in message:
                    return pattern
        return {}
    
    def get_domain_config(self, domain: str) -> Dict:
        """
        Get configuration for a domain.
        
        Args:
            domain: Domain key
            
        Returns:
            Domain configuration dict
        """
        return self.domains.get(domain, self.domains.get('general', {}))
    
    def get_thresholds_for_domain(self, domain: str) -> Dict:
        """
        Get thresholds for a domain.
        
        Args:
            domain: Domain key
            
        Returns:
            Threshold configuration dict
        """
        domain_config = self.get_domain_config(domain)
        return domain_config.get('thresholds', {})
    
    def get_intervention_config(self, domain: str) -> Dict:
        """
        Get intervention configuration for a domain.
        
        Args:
            domain: Domain key
            
        Returns:
            Intervention configuration dict
        """
        domain_config = self.get_domain_config(domain)
        return domain_config.get('interventions', {})
    
    def is_high_stakes(self, domain: str) -> bool:
        """
        Check if a domain is high-stakes.
        
        Args:
            domain: Domain key
            
        Returns:
            True if high-stakes
        """
        high_stakes_domains = {'finance', 'medical', 'legal', 'politics'}
        return domain in high_stakes_domains
    
    def get_all_domains(self) -> List[str]:
        """Get list of all domain keys."""
        return list(self.domains.keys())
    
    def get_domain_keywords(self, domain: str) -> List[str]:
        """
        Get keywords for a domain.
        
        Args:
            domain: Domain key
            
        Returns:
            List of keywords
        """
        domain_config = self.get_domain_config(domain)
        return domain_config.get('high_stakes_keywords', [])
