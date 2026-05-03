"""tests/test_bridge.py -- Bridge unit tests (mocked)."""
from unittest.mock import patch, MagicMock
from bridge.twin_api import list_schemas, create_twin, get_twin


def test_list_schemas_returns_list():
    with patch('bridge.twin_api.requests.get') as mock:
        mock.return_value = MagicMock(status_code=200, json=lambda:[
            {"type_name":"person"},{"type_name":"church"}
        ])
        mock.return_value.raise_for_status = lambda: None
        result = list_schemas()
        assert isinstance(result, list)
        assert len(result) == 2


def test_create_twin_returns_context():
    with patch('bridge.twin_api.requests.post') as mock:
        mock.return_value = MagicMock(status_code=201, json=lambda:{
            "twin_id":"abc123","twin_type":"person","display_name":"Jonah"
        })
        mock.return_value.raise_for_status = lambda: None
        result = create_twin("u001","Jonah","person")
        assert result["twin_type"] == "person"
        assert result["display_name"] == "Jonah"


def test_get_twin_not_found():
    with patch('bridge.twin_api.requests.get') as mock:
        mock.return_value = MagicMock(status_code=404)
        mock.return_value.raise_for_status.side_effect = Exception("404")
        result = get_twin("nonexistent")
        assert result is None
