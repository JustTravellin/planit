"""Entry point used by PyInstaller (it can't run a module with relative imports directly)."""
from p1s_controller.ui.app import main

if __name__ == "__main__":
    main()
