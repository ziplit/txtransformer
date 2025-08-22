"""
Test helper utilities
"""

from unittest.mock import MagicMock


class MockUnstructuredElement:
    """Mock for unstructured elements that behaves more like the real thing"""
    
    def __init__(self, text, element_type="Text", metadata=None):
        self._text = text
        self._element_type = element_type
        self.metadata = MockMetadata(metadata or {})
    
    def __str__(self):
        return self._text
    
    def __class__(self):
        class MockClass:
            __name__ = self._element_type
        return MockClass()


class MockMetadata:
    """Mock for unstructured metadata"""
    
    def __init__(self, data):
        self.data = data
    
    def to_dict(self):
        return self.data


def create_mock_element(text, element_type="Text", metadata=None):
    """Create a properly mocked unstructured element"""
    element = MagicMock()
    
    # Set the __str__ method correctly
    element.__str__.return_value = text
    
    # Create a mock type that returns the correct __name__
    mock_type = MagicMock()
    mock_type.__name__ = element_type
    element.__class__ = mock_type
    
    # Create mock metadata
    element.metadata = MagicMock()
    element.metadata.to_dict.return_value = metadata or {}
    
    return element