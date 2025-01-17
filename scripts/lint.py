import glob
import subprocess

IGNORED_FOLDERS = (".venv", ".venv310", ".venv311", "models", ".dev")
PYLINT_DISABLED = (
    "C0114",  # Missing module docstring
    "C0115",  # Missing class docstring
    "C0116",  # Missing function or method docstring
    "W2402",  # File name contains a non-ASCII character. (non-ascii-file-name)
)


def run_autoflake():
    print(
        "Running autoflake to clean up unused imports, variables, "
        + "and duplicate keys..."
    )
    python_files = glob.glob("**/*.py", recursive=True)
    for folder in IGNORED_FOLDERS:
        python_files = [file for file in python_files if folder not in file]
    if python_files:
        autoflake_args = [
            "autoflake",
            "--in-place",
            "--remove-unused-variables",
            "--remove-all-unused-imports",
            "--remove-duplicate-keys",
            "--expand-star-imports",
            "--ignore-pass-after-docstring",
        ] + python_files
        print("autoflake arguments:", " ".join(autoflake_args))
        subprocess.run(autoflake_args, check=True)
    else:
        print("No Python files found for autoflake.")


def run_black():
    print("Running black...")
    black_args = [
        "black",
        ".",
        "--exclude",
        "|".join(IGNORED_FOLDERS),
        "--line-length",
        "79",
    ]
    print("black arguments:", " ".join(black_args))
    subprocess.run(black_args, check=True)


def run_isort():
    print("Running isort...")
    isort_args = ["isort", "."] + [
        f"--skip={folder}" for folder in IGNORED_FOLDERS
    ]
    print("isort arguments:", " ".join(isort_args))
    subprocess.run(isort_args, check=True)


def run_flake8():
    print("Running flake8...")
    flake8_args = [
        "flake8",
        ".",
        "--exclude",
        ",".join(IGNORED_FOLDERS),
        "--ignore=E203,W503",
        # E203: whitespace before ':' (black compatibility)
        # W503: line break before binary operator (black compatibility)
        "--max-line-length=79",
    ]
    print("flake8 arguments:", " ".join(flake8_args))
    try:
        subprocess.run(flake8_args, check=True)
    except subprocess.CalledProcessError as e:
        print(f"flake8 failed with error: {e}")


def run_pylint():
    pylint_args = ["pylint", ".", "--ignore", ",".join(IGNORED_FOLDERS)] + [
        f"--disable={d}" for d in PYLINT_DISABLED
    ]
    print("Running pylint...")
    print("pylint arguments:", " ".join(pylint_args))
    result = subprocess.run(pylint_args, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode == 32:  # fatal error
        print(f"pylint failed with fatal error {result.returncode}")
        raise OSError("pylint failed with fatal error")
    if result.returncode != 0:
        print(f"pylint failed with exit status {result.returncode}")


def run_lint():
    run_autoflake()
    run_black()
    run_isort()
    # disable flake8 and pylint for now
    run_flake8()
    run_pylint()


if __name__ == "__main__":
    run_lint()
