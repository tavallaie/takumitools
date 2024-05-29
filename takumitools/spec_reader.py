import json
import requests

class SpecReader:
    def __init__(self, source):
        self.source = source

    def read_spec(self):
        """Reads the OpenAPI specification from a local file or a URL."""
        if self.source.startswith(('http://', 'https://')):
            return self._read_from_url()
        else:
            return self._read_from_file()

    def _read_from_file(self):
        """Reads the OpenAPI specification from a local file."""
        with open(self.source, 'r', encoding='utf-8') as file:
            return json.load(file)

    def _read_from_url(self):
        """Fetches the OpenAPI specification from a URL."""
        response = requests.get(self.source)
        response.raise_for_status()  # Ensure we notice bad responses
        return response.json()
