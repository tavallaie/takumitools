import requests

class APIClientBase:
    def __init__(self, base_url):
        self.base_url = base_url
        self.headers = {}  # Initialize an empty dictionary for headers

    def set_api_key(self, key_name, key_value):
        """Sets or updates the API key."""
        self.headers[key_name] = key_value

    def set_custom_header(self, header_name, header_value):
        """Allows users to set or update custom headers."""
        self.headers[header_name] = header_value
    
    def set_custom_headers(self, headers):
        """Sets or updates multiple custom headers at once."""
        self.headers.update(headers)    

    def make_request(self, method, path, **kwargs):
        """Makes an HTTP request with the configured headers."""
        headers = kwargs.pop('headers', {})
        headers.update(self.headers)  # Combine custom headers with any additional headers
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise SystemError(f"API request error: {e}")

