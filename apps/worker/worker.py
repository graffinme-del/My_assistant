import os
import time


def main() -> None:
    env = os.getenv("APP_ENV", "development")
    print(f"Worker started in {env} mode.")
    while True:
        # Placeholder for OCR/index/reminder jobs
        time.sleep(10)


if __name__ == "__main__":
    main()
