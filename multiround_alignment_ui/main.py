from .application import run_application
import sys

def main(args=sys.argv[1:]):
    if len(args) > 0:
        session_file = args[0]
    else:
        session_file = None
    run_application(session_file)


if __name__=="__main__":
    main()
