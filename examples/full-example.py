from pywhook import Webhook, WebhookError
import time
import sys


def handle_request(req):
    """Callback to be triggered when a new request arrives."""
    print("\n📥 New request received:")
    print(f"UUID: {req.get('uuid')}")
    print(f"Method: {req.get('method')}")
    print(f"Headers: {req.get('headers')}")
    print(f"Body: {req.get('content')}")


def main():
    try:
        # 1. Create a new token
        token_data = Webhook.create_token()
        token_id = token_data["uuid"]
        print(f"✅ Created token: {token_id}")

        # 2. Initialize Webhook client
        webhook = Webhook(token_id, auto_delete=True)

        # 3. Print available URLs
        print("\n🔗 Your webhook URLs:")
        for url in webhook.urls:
            print("   ", url)

        # 4. Set default response
        webhook.set_response("Webhook received successfully!", status=200)
        print("\n✅ Default response set.")

        # 5. Attach callback
        print("\n👂 Listening for incoming requests...")
        webhook.on_request(handle_request, interval=1.0)

        # 6. Wait for a request
        print(f"\n➡️ Send a POST request to: {webhook.url}")
        print("   Example: curl -X POST -d 'hello=world' ", webhook.url)

        try:
            req = webhook.wait_for_request(timeout=60)
            print("\n🎉 A request arrived within 60s!")
            print("UUID:", req.get("uuid"))
            print("Args:", req.get("content"))

            # 7. Try downloading attached files (if any)
            files = webhook.download_request_content(req)
            if files:
                print("\n📂 Downloaded files:")
                for key, file in files.items():
                    fname = f"{key}_{file['filename']}"
                    with open(fname, "wb") as f:
                        f.write(file["bytes"])
                    print(f"   Saved {fname} ({file['size']} bytes)")
            else:
                print("\n(no files attached)")

        except TimeoutError:
            print("\n⏳ No request received within timeout.")

    except WebhookError as e:
        print(f"\n❌ Webhook error: {e}")
        sys.exit(1)

    finally:
        # 8. Cleanup
        print("\n🧹 Cleaning up...")
        webhook.detach_all_callbacks()
        # auto_delete=True will delete token automatically on context exit
        print("✅ Done.")


if __name__ == "__main__":
    main()
