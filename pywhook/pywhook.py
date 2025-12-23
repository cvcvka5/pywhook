from typing import List, Dict, Any, Callable, Optional
import requests
import threading
import time


class WebhookError(Exception):
    """Custom error for webhook client."""


class Webhook:
    """
    A Python client for interacting with https://webhook.site.
    """

    BASE_URL = 'https://webhook.site'

    def __init__(self, uuid: str):
        """
        Initialize the Webhook with a token ID.

        Args:
            uuid (str): Unique token ID provided by webhook.site.
            auto_delete (bool): If True, token will be deleted on context exit.
        """
        if not isinstance(uuid, str):
            raise TypeError("Argument UUID must be of type string. \
If you passed create_token() directly make sure to pass create_token()['uuid'].")
        
        self.token_id = uuid
        self._on_request_threads: List[Dict[str, Any]] = []

    # ------------------- Token Management -------------------

    @staticmethod
    def create_token(**kwargs) -> Dict[str, Any]:
        try:
            res = requests.post(f"{Webhook.BASE_URL}/token", **kwargs)
            res.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to create token: {e}") from e

        if res.status_code != 201:
            raise WebhookError(f"Token creation failed: {res.status_code} {res.text}")
        return res.json()

    def delete_token(self) -> None:
        try:
            response = requests.delete(f'{self.BASE_URL}/token/{self.token_id}')
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to delete token: {e}") from e
        if response.status_code != 204:
            raise WebhookError(f"Unexpected response deleting token: {response.status_code}")

    def get_token_details(self) -> Dict[str, Any]:
        try:
            response = requests.get(f"{self.BASE_URL}/token/{self.token_id}")
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to fetch token details: {e}") from e
        return response.json()

    # ------------------- URL Helpers -------------------

    @property
    def url(self) -> str:
        return f"https://webhook.site/{self.token_id}"

    @property
    def urls(self) -> List[str]:
        template_urls = [
            "https://webhook.site/{uuid}",
            "https://{uuid}.webhook.site",
            "{uuid}@emailhook.site",
            "{uuid}.dnshook.site"
        ]
        return [url.format(uuid=self.token_id) for url in template_urls]

    # ------------------- Request Fetching -------------------

    def get_requests(
        self,
        sorting="newest",
        per_page=50,
        page=1,
        date_from=None,
        date_to=None,
        query=None
    ) -> List[Dict[str, Any]]:
        params = {
            "sorting": sorting,
            "per_page": per_page,
            "page": page,
            "date_from": date_from,
            "date_to": date_to,
            "query": query,
        }
        params = {k: v for k, v in params.items() if v is not None}
        try:
            response = requests.get(f'{self.BASE_URL}/token/{self.token_id}/requests', params=params)
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to fetch requests: {e}") from e
        return response.json()

    def get_latest_request(self) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get(f'{self.BASE_URL}/token/{self.token_id}/request/latest')
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to fetch latest request: {e}") from e
        return response.json()

    def wait_for_request(self, timeout: int = 15, interval: float = 0.1) -> Dict[str, Any]:
        latest_req = self.get_latest_request()
        latest_uuid = latest_req.get("uuid") if latest_req else None
        start_time = time.time()

        while time.time() - start_time < timeout:
            req = self.get_latest_request()
            if req and req.get("uuid") != latest_uuid:
                return req
            time.sleep(interval)

        raise TimeoutError(f"No new request after {timeout} seconds")

    # ------------------- Callbacks -------------------

    def on_request(self, callback: Callable[[Dict[str, Any]], None], interval: float = 0.1) -> None:
        def listen_to_requests(last_uuid: Optional[str]):
            while not kill_event.is_set():
                try:
                    req = self.get_latest_request()
                    if req and req.get("uuid") != last_uuid:
                        callback(req)
                        last_uuid = req.get("uuid")
                except WebhookError as e:
                    # Could add logging here instead of silent fail
                    pass
                time.sleep(interval)

        kill_event = threading.Event()
        latest_req = self.get_latest_request()
        last_uuid = latest_req.get("uuid") if latest_req else None

        thread = threading.Thread(target=listen_to_requests, args=(last_uuid,), daemon=True)
        self._on_request_threads.append({"thread": thread, "kill_event": kill_event})
        thread.start()

    @property
    def callbacks_on_request(self) -> List[Dict[str, Any]]:
        return self._on_request_threads

    def detach_callback(self, index: int) -> List[Dict[str, Any]]:
        if index >= len(self._on_request_threads):
            raise IndexError("Callback index out of range.")
        self._on_request_threads[index]["kill_event"].set()
        self._on_request_threads[index]["thread"].join()
        self._on_request_threads.pop(index)
        return self.callbacks_on_request

    def detach_all_callbacks(self) -> None:
        for entry in self._on_request_threads:
            entry["kill_event"].set()
            entry["thread"].join()
        self._on_request_threads.clear()

    # ------------------- Response Control -------------------

    def set_response(self, content, status=200, content_type="text/plain") -> Dict[str, Any]:
        url = f"{self.BASE_URL}/token/{self.token_id}"
        payload = {
            "default_content": content,
            "default_status": status,
            "default_content_type": content_type,
        }
        try:
            res = requests.put(url, json=payload)
            res.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to set response: {e}") from e
        return res.json()

    def download_request_content(self, request: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        request_id = request.get('uuid') or request.get('id')
        if not request_id:
            raise WebhookError("Request object missing 'uuid' or 'id'.")

        files = request.get("files", {})
        if not files:
            return {}

        out = {}
        for key, file in files.items():
            url = f"{self.BASE_URL}/token/{self.token_id}/request/{request_id}/download/{file['id']}"
            try:
                response = requests.get(url)
                response.raise_for_status()
            except requests.RequestException as e:
                raise WebhookError(f"Failed to download file {file['id']}: {e}") from e
            out[key] = {
                "id": file['id'],
                "filename": file['filename'],
                "name": file['name'],
                "bytes": response.content,
                "size": file['size'],
                "content_type": file['content_type'],
            }
        return out

    # ------------------- Context Manager -------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.detach_all_callbacks()
        self.delete_token()
