# pywhook

`pywhook` is a Python client library for interacting with [webhook.site](https://webhook.site),
allowing you to easily create webhook tokens, receive requests, set custom responses,
and manage webhook listeners asynchronously.

## Features

- Create and delete webhook tokens.
- Retrieve requests received by a token.
- Wait for incoming webhook requests.
- Attach callbacks that trigger on new requests.
- Customize default responses.
- Thread-safe listener management.
- Context manager support for automatic cleanup.

## Installation

```bash
pip install pywhook
```

## Usage

```python
    from pywhook import Webhook 
    import pprint
    import time

    pp = pprint.PrettyPrinter(indent=2)

    # Create a new webhook token
    print("Creating a new token...")
    token_data = Webhook.create_token()
    pp.pprint(token_data)

    token_id = token_data.get("uuid")
    if not token_id:
        print("Failed to create token. Exiting test.")
        exit(1)

    # Initialize webhook instance
    webhook = Webhook(token_id)
    print(f"Using webhook URL: {webhook.url}")

    # Get token details
    print("\nGetting token details...")
    details = webhook.get_token_details()
    pp.pprint(details)

    # Set a default response
    print("\nSetting default response...")
    resp = webhook.set_response(content="Hello from test!", status=201, content_type="text/plain")
    pp.pprint(resp)

    # Get URLs formats
    print("\nWebhook URLs:")
    for url in webhook.urls:
        print(url)

    # Fetch requests (should be empty initially)
    print("\nFetching requests...")
    requests_list = webhook.get_requests()
    pp.pprint(requests_list)

    print("\nTesting wait_for_request (no exception expected)...")
    print(webhook.wait_for_request(timeout=10))
    

    # Test wait_for_request with a timeout (expect timeout error since no request will come)
    print("\nTesting wait_for_request (expecting timeout)...")
    try:
        webhook.wait_for_request(timeout=1)
    except TimeoutError as e:
        print(f"Timeout as expected: {e}")

    # Define a callback function for on_request
    def my_callback(req):
        print("\nCallback triggered for new request:")
        pp.pprint(req)

    # Start listening for new requests
    print("\nStarting on_request listener thread (will listen for 5 seconds)...")
    webhook.on_request(my_callback)

    # Normally, here you would send a test request to webhook.url externally
    # For testing, we just wait to simulate listening
    time.sleep(5)

    # Detach all callbacks (stop listening)
    print("\nDetaching all callbacks...")
    webhook.detach_all_callbacks()

    # Finally, delete the token to clean up
    print("\nDeleting token...")
    webhook.delete_token()
    print("Test complete. All tests passed. No issues present.")
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Ulus Vatansever (cvcvka5)