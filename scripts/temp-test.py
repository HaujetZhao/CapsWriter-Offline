import subprocess
from time import sleep

if __name__ != "__main__":
    raise ImportError(f"Script {__file__} should not be imported as a module")


def run_server():
    server_args = ["python", "./start_server.py"]
    server_process = subprocess.Popen(server_args)
    sleep(30)
    return server_process


def run_client():
    print("Starting client")
    client_args = [
        "python",
        "./start_client.py",
        "./../../../../temp/chinese-speech-example/2025-01-16_04-20-03.mov",
    ]
    client_process = subprocess.Popen(client_args)
    return client_process


server_process = run_server()
client_process = run_client()

# Wait for the client to run for 15 seconds
sleep(15)

# Terminate both processes
client_process.terminate()
server_process.terminate()
