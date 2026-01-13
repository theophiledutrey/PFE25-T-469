import sys
import os

# Ensure the current directory is in the python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """
    Entry point for the REEF application.
    - 'reef' -> Runs the GUI (main.py)
    - 'reef --cli' -> Runs the CLI (cli/reef.py)
    - 'reef [command]' -> Runs the CLI command
    """
    
    # Check if we should run CLI
    # Conditions:
    # 1. '--cli' is passed
    # 2. Arguments are provided (implying a CLI command like 'reef deploy')
    #    Exception: 'reef' with no args runs GUI.
    
    use_cli = False
    
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        use_cli = True
    elif len(sys.argv) > 1:
        # If there are arguments, default to CLI
        use_cli = True
        
    if use_cli:
        try:
            from cli.reef import cli
            cli()
        except ImportError as e:
            print(f"Error importing CLI module: {e}")
            sys.exit(1)
    else:
        try:
            from main import run_app
            run_app()
        except ImportError as e:
            print(f"Error importing Main GUI module: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
