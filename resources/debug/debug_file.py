import runpy
import sys
import os

print(f"Launching {sys.argv[1]} ...")
os.environ["DEBUGPY_LOG_DIR"] = "/home/rich/source/debugpyweb/temp/"
os.environ["PYDEVD_DEBUG"] = "1"
os.environ["PYDEVD_DEBUG_FILE"] = "/home/rich/source/debugpyweb/temp/"

# Wait for VS code to attach to our socket
import debugpy
debugpy.connect(5768) # Number is actually irrelevant
debugpy.wait_for_client()

print("Launch complete")

# Run the actual file we're debugging
runpy.run_module(sys.argv[1], run_name="__main__", alter_sys=True)

