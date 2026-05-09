OML_DIR="${0:A:h}"

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

    local OML_VENV_DIR="$OML_DIR/venv"
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

    if [ ! -f "$OML_DIR/config.json" ]; then
        echo "Oh-my-llm is not configured. Please run 'oml config' to set it up." >&2
    fi

    oml_clear
}

oml_clear() {
    OML_MESSAGES_FILE="$(mktemp -p "$OML_DIR/messages" "oml_messages_$(date +%Y%m%d%H%M%S)_XXXXXX")"
    mv "$OML_MESSAGES_FILE" "$OML_MESSAGES_FILE.json"
    OML_MESSAGES_FILE="$OML_MESSAGES_FILE.json"
    echo "[]" > "$OML_MESSAGES_FILE"
}

if oml_init; then
    oml() {
        if [ "$1" = "clear" ]; then
            oml_clear
            return
        fi
        if [ "$1" = "upgrade" ]; then
            cd "$OML_DIR" && git pull && source ~/.zshrc
            return
        fi
        "$OML_PYTHON" "$OML_DIR/oml.py" "$@"
    }

    command_not_found_handler() {
        "$OML_PYTHON" "$OML_DIR/oml.py" execute "$*" "$OML_MESSAGES_FILE"
    }

    autoload -Uz add-zsh-hook

    oml_preexec_hook() {
        OML_PREV_COMMAND="$1"
    }

    oml_precmd_hook() {
        if [ $? -ne 0 ] && [ $? -ne 130 ] && [ -n "$OML_PREV_COMMAND" ]; then
            "$OML_PYTHON" "$OML_DIR/oml.py" execute --failed-command "$OML_PREV_COMMAND" "$OML_MESSAGES_FILE"
        fi
        OML_PREV_COMMAND=""
    }

    add-zsh-hook preexec oml_preexec_hook
    add-zsh-hook precmd oml_precmd_hook

    what() {
        return 127
    }

    who() {
        return 127
    }
fi
