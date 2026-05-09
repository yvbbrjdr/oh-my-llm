# oh-my-llm

Infuse your zsh with AI

oh-my-llm is a zsh plugin that brings a large language model directly into your shell. Type natural language instead of commands and run web searches and fetches, all without leaving your terminal.

## Features

- **Natural language commands**: type a question or instruction at the prompt and the AI responds or runs the right command for you
- **Tool use**: the AI can execute shell commands (with your approval), search the web, and fetch web pages
- **Configurable backend**: works with OpenAI or any OpenAI-compatible API endpoint

## Requirements

- zsh
- Python 3.8+ with `venv` and `pip`
- An [OpenAI API key](https://platform.openai.com/api-keys) (or a compatible provider)
- _(Optional)_ An [Exa API key](https://exa.ai/) for web search and page fetching

## Installation

### With oh-my-zsh

**1. Clone the repository into your oh-my-zsh custom plugins directory:**

```zsh
git clone https://github.com/yvbbrjdr/oh-my-llm ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/oh-my-llm
```

**2. Add `oh-my-llm` to the plugins list in your `~/.zshrc`:**

```zsh
plugins=(... oh-my-llm)
```

**3. Reload your shell:**

```zsh
omz reload
```

### Without oh-my-zsh

**1. Clone the repository anywhere you like:**

```zsh
git clone https://github.com/yvbbrjdr/oh-my-llm ~/.oh-my-llm
```

**2. Source the plugin from your `~/.zshrc`:**

```zsh
source ~/.oh-my-llm/oh-my-llm.plugin.zsh
```

**3. Reload your shell:**

```zsh
source ~/.zshrc
```

The plugin will automatically create a virtual environment and install its dependencies on first load.

**4. Configure your API keys:**

```zsh
oml config
```

This opens a JSON config file in your `$EDITOR`. Fill in your credentials.

## Usage

### Natural language at the prompt

Just type what you want. If it isn't a valid shell command, oh-my-llm handles it:

```
$ what is my public IP address?
$ find all PDFs modified in the last week
$ summarize the contents of README.md
$ convert photo.heic to JPEG
$ convert all PNGs in this folder to WebP
$ compress video.mov to an MP4 under 50MB
$ extract the audio from recording.mp4 as an MP3
$ what does the -r flag do in rsync?
$ who owns the process on port 8080?
```

### Session management

Conversation context persists for your entire shell session. To clear the history and start a new conversation:

```zsh
oml_clear
```

## Security

Shell commands proposed by the AI require your explicit approval before execution. When `skip_readonly_command_verification` is enabled, read-only commands (e.g. `ls`, `cat`, `grep`) are confirmed automatically and run without a prompt; commands that modify the system always require approval.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
