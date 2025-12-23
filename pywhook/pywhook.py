from typing import List, Dict, Any, Callable, Optional
import requests
import threading
import time


class WebhookError(Exception):
    """Raised when an operation against webhook.site fails."""


class Webhook:
    """
    Lightweight Python client for interacting with https://webhook.site.

    Provides:

    - Token creation and deletion
    - Request polling and background callbacks
    - Default response configuration
    - Automatic cleanup via context manager

    Example
    -------
    >>> token_data = Webhook.create_token()
    >>> with Webhook(token_data["uuid"]) as hook:
    ...     print(hook.url)
    ...     req = hook.wait_for_request(timeout=10)
    ...     print(req)
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
        This constructor validates the token type strictly. A common mistake
        is passing the result of `create_token()` directly; you should pass
        `create_token()['uuid']`.
        """
        if not isinstance(uuid, str):
            raise TypeError(
                "Argument UUID must be a string. "
                "If you passed create_token() directly, use create_token()['uuid']."
            )

        self.token_id = uuid
        self._on_request_threads: List[Dict[str, Any]] = []  # Tracks background callbacks

    # ------------------- Token Management -------------------

    @staticmethod
    def create_token(**kwargs) -> Dict[str, Any]:
        """
        Create a new webhook token.

        Parameters
        ----------
        **kwargs
            Optional arguments to forward to requests.post (headers, auth, etc.)

        Returns
        -------
        dict
            Full JSON response from webhook.site including the UUID.

        Raises
        ------
        WebhookError
            If the token could not be created.
        """
        try:
            res = requests.post(f"{Webhook.BASE_URL}/token", **kwargs)
            res.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to create token: {e}") from e

        if res.status_code != 201:
            raise WebhookError(f"Token creation failed: {res.status_code} {res.text}")

        return res.json()

    def delete_token(self) -> None:
        """
        Permanently delete the webhook token.

        Automatically called when exiting the context manager.

        Raises
        ------
        WebhookError
            If deletion fails or returns an unexpected status.
        """
        try:
            response = requests.delete(f"{self.BASE_URL}/token/{self.token_id}")
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to delete token: {e}") from e

        if response.status_code != 204:
            raise WebhookError(f"Unexpected response deleting token: {response.status_code}")

    def get_token_details(self) -> Dict[str, Any]:
        """
        Fetch metadata and configuration for the token.

        Returns
        -------
        dict
            JSON response from webhook.site describing the token.

        Raises
        ------
        WebhookError
            If the request fails.
        """
        try:
            response = requests.get(f"{self.BASE_URL}/token/{self.token_id}")
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to fetch token details: {e}") from e

        return response.json()

    # ------------------- URL Helpers -------------------

    @property
    def url(self) -> str:
        """
        Return the primary webhook URL.

        Returns
        -------
        str
            The main webhook.site URL for this token.
        """
        return f"https://webhook.site/{self.token_id}"

    @property
    def urls(self) -> List[str]:
        """
        Return a list of alternative webhook endpoints.

        Returns
        -------
        List[str]
            Fully-formatted URLs and hook endpoints.
        """
        templates = [
            "https://webhook.site/{uuid}",
            "https://{uuid}.webhook.site",
            "{uuid}@emailhook.site",
            "{uuid}.dnshook.site",
        ]
        return [t.format(uuid=self.token_id) for t in templates]

    # ------------------- Request Fetching -------------------

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

        Parameters
        ----------
        sorting : str
            How to sort requests ('newest' or 'oldest').
        per_page : int
            Number of results per page.
        page : int
            Page number to fetch.
        date_from : optional
            Start date filter.
        date_to : optional
            End date filter.
        query : optional
            Search query filter.

        Returns
        -------
        List[Dict[str, Any]]
            List of request objects.

        Raises
        ------
        WebhookError
            If fetching requests fails.
        """
        params = {k: v for k, v in locals().items() if v is not None and k != "self"}

        try:
            response = requests.get(
                f"{self.BASE_URL}/token/{self.token_id}/requests", params=params
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to fetch requests: {e}") from e

        return response.json()

    def get_latest_request(self) -> Optional[Dict[str, Any]]:
        """
        Return the most recent request.

        Returns
        -------
        dict or None
            The latest request, or None if no requests exist.

        Raises
        ------
        WebhookError
            If the request fails.
        """
        try:
            response = requests.get(f"{self.BASE_URL}/token/{self.token_id}/request/latest")
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to fetch latest request: {e}") from e

        return response.json()

    def wait_for_request(self, timeout: int = 15, interval: float = 0.1) -> Dict[str, Any]:
        """
        Block until a new request arrives or timeout is reached.

        Parameters
        ----------
        timeout : int
            Maximum seconds to wait.
        interval : float
            Polling interval in seconds.

        Returns
        -------
        dict
            The new request object.

        Raises
        ------
        TimeoutError
            If no new request arrives within the timeout.
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

    # ------------------- Callbacks -------------------

    def on_request(self, callback: Callable[[Dict[str, Any]], None], interval: float = 0.1) -> None:
        """
        Register a callback that fires for every new request.

        Parameters
        ----------
        callback : Callable[[dict], None]
            Function called with the request dictionary.
        interval : float
            How often to poll for new requests (seconds).

        Notes
        -----
        The callback runs in a background daemon thread. Transient API errors
        are ignored, so your function may miss some requests if the API fails.
        """
        def listener(last_uuid: Optional[str]):
            while not kill_event.is_set():
                try:
                    req = self.get_latest_request()
                    if req and req.get("uuid") != last_uuid:
                        callback(req)
                        last_uuid = req.get("uuid")
                except WebhookError:
                    pass
                time.sleep(interval)

        kill_event = threading.Event()
        latest = self.get_latest_request()
        last_uuid = latest.get("uuid") if latest else None

        thread = threading.Thread(target=listener, args=(last_uuid,), daemon=True)
        self._on_request_threads.append({"thread": thread, "kill_event": kill_event})
        thread.start()

    @property
    def callbacks_on_request(self) -> List[Dict[str, Any]]:
        """Return a list of active request listener threads and kill events."""
        return self._on_request_threads

    def detach_callback(self, index: int) -> List[Dict[str, Any]]:
        """
        Stop and remove a callback by its index.

        Parameters
        ----------
        index : int
            Index of the callback to remove.

        Returns
        -------
        List[Dict[str, Any]]
            Updated list of active callbacks.

        Raises
        ------
        IndexError
            If the index is out of range.
        """
        if index >= len(self._on_request_threads):
            raise IndexError("Callback index out of range.")

        entry = self._on_request_threads[index]
        entry["kill_event"].set()
        entry["thread"].join()
        self._on_request_threads.pop(index)
        return self.callbacks_on_request

    def detach_all_callbacks(self) -> None:
        """Stop and remove all active request callbacks."""
        for entry in self._on_request_threads:
            entry["kill_event"].set()
            entry["thread"].join()
        self._on_request_threads.clear()

    # ------------------- Response Control -------------------

    def set_response(self, content: str, status: int = 200, content_type: str = "text/plain") -> Dict[str, Any]:
        """
        Configure the default response for the webhook.

        Parameters
        ----------
        content : str
            Default response content.
        status : int
            HTTP status code.
        content_type : str
            MIME type of the response.

        Returns
        -------
        dict
            JSON response confirming the update.

        Raises
        ------
        WebhookError
            If the request fails.
        """
        payload = {"default_content": content, "default_status": status, "default_content_type": content_type}

        try:
            res = requests.put(f"{self.BASE_URL}/token/{self.token_id}", json=payload)
            res.raise_for_status()
        except requests.RequestException as e:
            raise WebhookError(f"Failed to set response: {e}") from e

        return res.json()

    def download_request_content(self, request: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Download uploaded files attached to a request.

        Parameters
        ----------
        request : dict
            Request object returned by webhook.site API.

        Returns
        -------
        dict[str, dict]
            Mapping of file keys to their data including bytes, filename, and content type.

        Raises
        ------
        WebhookError
            If request object is invalid or download fails.
        """
        request_id = request.get("uuid") or request.get("id")
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
                "id": file["id"],
                "filename": file["filename"],
                "name": file["name"],
                "bytes": response.content,
                "size": file["size"],
                "content_type": file["content_type"],
            }
        return out

    # ------------------- Context Manager -------------------

    def __enter__(self) -> "Webhook":
        """Allow usage via `with Webhook(...) as hook:`."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Ensure all callbacks are stopped and the token is deleted
        when leaving the context.
        """
        self.detach_all_callbacks()
        self.delete_token()
