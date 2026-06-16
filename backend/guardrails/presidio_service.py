"""
presidio_service.py — Implementation for PII detection.
"""
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine
from monitoring.logger import get_logger

logger = get_logger(__name__)

_analyzer = None
_anonymizer = None

def get_analyzer():
    global _analyzer
    if _analyzer is None:
        logger.info("Initializing Presidio Analyzer")
        _analyzer = AnalyzerEngine()
        
        # Add custom password recognizer
        password_pattern = Pattern(
            name="password_pattern",
            regex=r"(?i)(password|pwd|secret)\s*(is|:|=)\s*([^\s]+)",
            score=0.8
        )
        password_recognizer = PatternRecognizer(
            supported_entity="PASSWORD",
            patterns=[password_pattern]
        )
        _analyzer.registry.add_recognizer(password_recognizer)
        
    return _analyzer

def get_anonymizer():
    global _anonymizer
    if _anonymizer is None:
        logger.info("Initializing Presidio Anonymizer")
        _anonymizer = AnonymizerEngine()
    return _anonymizer

def detect_pii(text: str) -> list:
    if not text:
        return []
    analyzer = get_analyzer()
    return analyzer.analyze(text=text, language="en")

def anonymize_text(text: str, pii_results: list = None) -> str:
    if not text:
        return text
    if pii_results is None:
        pii_results = detect_pii(text)
    if not pii_results:
        return text
    
    anonymizer = get_anonymizer()
    result = anonymizer.anonymize(text=text, analyzer_results=pii_results)
    return result.text
