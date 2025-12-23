from typing import List, Dict, Any, Callable, Optional
import requests
import threading
import time


class WebhookError(Exception):
    """Raised when an operation against webhook.site fails."""


class Webhook:
    """
    Lightweight Python client for interacting with https://webhook.site.

    This class wraps the webhook.site HTTP API and provides:
    - Token creation and deletion
    - Request polling and callbacks
    - Simple response configuration
    - Automatic cleanup via context manager
    """

    BASE_URL = "https://webhook.site"

    def __init__(self, uuid: str):
        """
        Create a Webhook instance using an existing webhook token.

        Parameters
        ----------
        uuid : str
            The webhook token UUID provided by webhook.site.

        Notes
        -----
        This constructor intentionally validates the token type strictly.
        Passing the result of `create_token()` directly is a common mistake;
        make sure to pass `create_token()['uuid']` instead.
        """
        if not isinstance(uuid, str):
            raise TypeError(
                "Argument UUID must be a string. "
                "If you passed create_token() directly, use create_token()['uuid']."
            )

        self.token_id = uuid

        # Tracks background threads created via `on_request`
        self._on_request_threads: List[Dict[str, Any]] = []

    # Token management
    @staticmethod
    def create_token(**kwargs) -> Dict[str, Any]:
        """
        Create a new webhook token on webhook.site.

        Any keyword arguments are forwarded directly to the API request
        (for example, headers or auth options).

        Returns
        -------
        dict
            Full JSON response returned by webhook.site, including the UUID.
        """
        try:
            res = requests.post(f"{Webhook.BASE_URL}/token", **kwargs)
            res.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to create token: {e}") from e

        if res.status_code != 201:
            raise WebhookError(
                f"Token creation failed: {res.status_code} {res.text}"
            )

        return res.json()

    def delete_token(self) -> None:
        """
        Permanently delete the webhook token.

        This is automatically called when exiting the context manager.
        """
        try:
            response = requests.delete(
                f"{self.BASE_URL}/token/{self.token_id}"
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to delete token: {e}") from e

        if response.status_code != 204:
            raise WebhookError(
                f"Unexpected response deleting token: {response.status_code}"
            )

    def get_token_details(self) -> Dict[str, Any]:
        """
        Fetch metadata and configuration for the current token.
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/token/{self.token_id}"
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to fetch token details: {e}") from e

        return response.json()

    # URL helpers
    @property
    def url(self) -> str:
        """
        Primary webhook URL.
        """
        return f"https://webhook.site/{self.token_id}"

    @property
    def urls(self) -> List[str]:
        """
        Common alternative endpoints supported by webhook.site.

        Returns
        -------
        list[str]
            A list of fully-formatted URLs and hook endpoints.
        """
        templates = [
            "https://webhook.site/{uuid}",
            "https://{uuid}.webhook.site",
            "{uuid}@emailhook.site",
            "{uuid}.dnshook.site",
        ]
        return [t.format(uuid=self.token_id) for t in templates]

    # Request fetching
    def get_requests(
        self,
        sorting: str = "newest",
        per_page: int = 50,
        page: int = 1,
        date_from=None,
        date_to=None,
        query=None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch previously received requests for this webhook.
        """
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
            response = requests.get(
                f"{self.BASE_URL}/token/{self.token_id}/requests",
                params=params,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to fetch requests: {e}") from e

        return response.json()

    def get_latest_request(self) -> Optional[Dict[str, Any]]:
        """
        Return the most recent request, or None if no requests exist yet.
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/token/{self.token_id}/request/latest"
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(
                f"Failed to fetch latest request: {e}"
            ) from e

        return response.json()

    def wait_for_request(
        self, timeout: int = 15, interval: float = 0.1
    ) -> Dict[str, Any]:
        """
        Block until a new request arrives or the timeout is reached.
        """
        latest = self.get_latest_request()
        last_uuid = latest.get("uuid") if latest else None
        start = time.time()

        while time.time() - start < timeout:
            req = self.get_latest_request()
            if req and req.get("uuid") != last_uuid:
                return req
            time.sleep(interval)

        raise TimeoutError(f"No new request after {timeout} seconds")

    # Callbacks
    def on_request(
        self,
        callback: Callable[[Dict[str, Any]], None],
        interval: float = 0.1,
    ) -> None:
        """
        Register a callback that fires whenever a new request arrives.

        The callback runs in a background thread and receives the request
        payload as a dictionary.
        """

        def listen(last_uuid: Optional[str]):
            while not kill_event.is_set():
                try:
                    req = self.get_latest_request()
                    if req and req.get("uuid") != last_uuid:
                        callback(req)
                        last_uuid = req.get("uuid")
                except WebhookError:
                    # Ignore transient API errors and keep listening
                    pass
                time.sleep(interval)

        kill_event = threading.Event()
        latest = self.get_latest_request()
        last_uuid = latest.get("uuid") if latest else None

        thread = threading.Thread(
            target=listen,
            args=(last_uuid,),
            daemon=True,
        )

        self._on_request_threads.append(
            {"thread": thread, "kill_event": kill_event}
        )
        thread.start()

    @property
    def callbacks_on_request(self) -> List[Dict[str, Any]]:
        """
        Return currently active request listeners.
        """
        return self._on_request_threads

    def detach_callback(self, index: int) -> List[Dict[str, Any]]:
        """
        Stop and remove a single callback by index.
        """
        if index >= len(self._on_request_threads):
            raise IndexError("Callback index out of range.")

        entry = self._on_request_threads[index]
        entry["kill_event"].set()
        entry["thread"].join()
        self._on_request_threads.pop(index)

        return self.callbacks_on_request

    def detach_all_callbacks(self) -> None:
        """
        Stop and remove all active callbacks.
        """
        for entry in self._on_request_threads:
            entry["kill_event"].set()
            entry["thread"].join()

        self._on_request_threads.clear()

    # Response control
    def set_response(
        self,
        content,
        status: int = 200,
        content_type: str = "text/plain",
    ) -> Dict[str, Any]:
        """
        Configure the default response returned by the webhook.
        """
        payload = {
            "default_content": content,
            "default_status": status,
            "default_content_type": content_type,
        }

        try:
            res = requests.put(
                f"{self.BASE_URL}/token/{self.token_id}",
                json=payload,
            )
            res.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to set response: {e}") from e

        return res.json()

    def download_request_content(
        self, request: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Download uploaded files attached to a request.
        """
        request_id = request.get("uuid") or request.get("id")
        if not request_id:
            raise WebhookError(
                "Request object missing 'uuid' or 'id'."
            )

        files = request.get("files", {})
        if not files:
            return {}

        out = {}
        for key, file in files.items():
            url = (
                f"{self.BASE_URL}/token/{self.token_id}"
                f"/request/{request_id}/download/{file['id']}"
            )
            try:
                response = requests.get(url)
                response.raise_for_status()
            except requests.RequestException as e:
                raise WebhookError(
                    f"Failed to download file {file['id']}: {e}"
                ) from e

            out[key] = {
                "id": file["id"],
                "filename": file["filename"],
                "name": file["name"],
                "bytes": response.content,
                "size": file["size"],
                "content_type": file["content_type"],
            }

        return out

    # Context manager
    def __enter__(self):
        """
        Allow usage via `with Webhook(...) as hook:`.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Ensure all callbacks are stopped and the token is deleted
        when leaving the context.
        """
        self.detach_all_callbacks()
        self.delete_token()
