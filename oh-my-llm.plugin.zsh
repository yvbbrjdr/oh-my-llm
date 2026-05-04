OML_DIR="${0:A:h}"
OML_VENV_DIR="$OML_DIR/venv"
OML_TEMP_DIR="$OML_DIR/temp"

oml_init() {
    if command -v /opt/homebrew/bin/python3 &> /dev/null; then
        OML_PYTHON=/opt/homebrew/bin/python3
    elif command -v python3 &> /dev/null; then
        OML_PYTHON=python3
    elif command -v python &> /dev/null; then
        OML_PYTHON=python
    else
        echo "No suitable Python interpreter found. Oh-my-llm is not loaded." >&2
        return 1
    fi

    if ! "$OML_PYTHON" -m venv -h &> /dev/null; then
        echo "Python venv module is not available. Oh-my-llm is not loaded." >&2
        return 1
    fi

    if ! "$OML_PYTHON" -m pip --version &> /dev/null; then
        echo "pip is not available. Oh-my-llm is not loaded." >&2
        return 1
    fi

    if [ ! -d "$OML_VENV_DIR" ]; then
        echo "Creating virtual environment for oh-my-llm..."
        if ! "$OML_PYTHON" -m venv "$OML_VENV_DIR"; then
            echo "Failed to create virtual environment. Oh-my-llm is not loaded." >&2
            return 1
        fi
    fi

    OML_PYTHON="$OML_VENV_DIR/bin/python"

    if ! "$OML_PYTHON" "$OML_DIR/check_deps.py" &> /dev/null; then
        echo "Installing oh-my-llm dependencies..."
        if ! "$OML_PYTHON" -m pip install -r "$OML_DIR/requirements.txt"; then
            echo "Failed to install dependencies. Oh-my-llm is not loaded." >&2
            return 1
        fi
    fi

    OML_MESSAGES="[]"

    alias oml="$OML_PYTHON $OML_DIR/oml.py"
    alias oml-clear="OML_MESSAGES='[]'"
}

if oml_init; then
    command_not_found_handler() {
        local NEXT_MESSAGES="$(mktemp -p "$OML_TEMP_DIR" "next_messages_XXXXXX")"
        if "$OML_PYTHON" "$OML_DIR/oml.py" execute "$*" "$OML_MESSAGES" "$NEXT_MESSAGES"; then
            OML_MESSAGES="$(cat "$NEXT_MESSAGES")"
        fi
        rm -f "$NEXT_MESSAGES"
    }
fi
