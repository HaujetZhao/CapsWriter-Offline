# #TODO: CONST var for excluded folders. (.venv, etc)

import glob
import subprocess


def run_autoflake():
    print(
        "Running autoflake to clean up unused imports, variables, and duplicate keys..."
    )
    # Expand the **/*.py pattern using glob
    python_files = glob.glob("**/*.py", recursive=True)

    # exclude folder .venv
    python_files = [file for file in python_files if ".venv" not in file]
    python_files = [file for file in python_files if ".venv310" not in file]
    python_files = [file for file in python_files if ".venv311" not in file]

    # Run autoflake only if there are Python files
    if python_files:
        subprocess.run(
            [
                "autoflake",
                "--in-place",
                "--remove-unused-variables",
                "--remove-all-unused-imports",
                "--remove-duplicate-keys",
                "--expand-star-imports",
                "--ignore-pass-after-docstring",
            ]
            + python_files,
            check=True,
        )
    else:
        print("No Python files found for autoflake.")


def run_black():
    print("Running black...")
    subprocess.run(["black", ".", "--exclude", ".venv|.venv310|.venv311"], check=True)


def run_isort():
    print("Running isort...")
    subprocess.run(
        ["isort", ".", "--skip", ".venv", "--skip", ".venv310", "--skip", ".venv311"],
        check=True,
    )


def run_flake8():
    print("Running flake8...")
    try:
        subprocess.run(
            [
                "flake8",
                ".",
                "--exclude",
                ".venv,.venv310,.venv311",
                "--max-line-length=79",
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"flake8 failed with error: {e}")


def run_pylint():
    print("Running pylint...")
    try:
        subprocess.run(
            ["pylint", ".", "--ignore", ".venv,.venv310,.venv311"], check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"pylint failed with error: {e}")


def run_lint():
    run_autoflake()
    run_black()
    run_isort()
    # disable flake8 and pylint for now
    run_flake8()
    run_pylint()


if __name__ == "__main__":
    run_lint()
