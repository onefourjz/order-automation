#!/usr/bin/env python3
"""
Spectacle Order Automation - Launcher Script
Run this script to start the application.

Tries to launch the GUI with tkinter first.
If tkinter is not available, starts a web-based UI instead.
"""

import os
import sys
import subprocess


def check_dependencies():
    """Check if required packages are installed."""
    required = {
        "pdfplumber": None,
        "selenium": None,
        "webdriver_manager": None,
        "yaml": "PyYAML",
        "PIL": "Pillow",
    }

    missing = []
    for package, install_name in required.items():
        try:
            __import__(package)
        except ImportError:
            missing.append(install_name or package)

    if missing:
        print("Missing required packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\nInstalling missing packages...")
        req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", req_file]
        )
        print("✅ Dependencies installed successfully!")
        return True

    return True


def try_launch_gui():
    """Try to launch the tkinter GUI."""
    try:
        import tkinter
        print("Starting desktop application...")
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from main_app import main
        main()
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"⚠ GUI launch failed: {e}")
        return False


def launch_web_app():
    """Launch the web-based UI as fallback."""
    print("\n" + "=" * 60)
    print("  tkinter not available - starting web-based UI")
    print("=" * 60)
    print()

    # Check if flask is installed
    try:
        import flask
    except ImportError:
        print("Installing Flask for web UI...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "flask"]
        )
        print("✅ Flask installed!")

    print("Starting web server...")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    try:
        from web_app import main
        main()
    except Exception as e:
        print(f"Error starting web app: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")


def main():
    """Main launcher."""
    print("=" * 60)
    print("  Spectacle Order Automation")
    print("  VSP PDF → Eyefinity Order Entry")
    print("=" * 60)
    print()

    # Check dependencies
    print("Checking dependencies...")
    try:
        check_dependencies()
        print("✅ All dependencies satisfied.")
    except Exception as e:
        print(f"⚠ Dependency check warning: {e}")
    print()

    # Try GUI first, fall back to web app
    if not try_launch_gui():
        print("ℹ tkinter module not available on this system.")
        print("  Falling back to web-based UI...")
        print()
        launch_web_app()


if __name__ == "__main__":
    main()