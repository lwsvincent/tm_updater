"""Mock application for testing the launcher module."""
import sys
import time


def main() -> None:
    print(f"App launched with args: {sys.argv[1:]}")
    time.sleep(3)
    print("App exiting.")


if __name__ == "__main__":
    main()
