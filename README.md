# chtext

A command-line tool for generating short, quotable English translations from classical Chinese texts. Powered by the [Chinese Text Project](https://ctext.org) API.

```
$ chtext generate
"Knowing the male and guarding the female are the streams of the world."
  -- Dao De Jing (道德經), 道德經
```

## Features

- **Short quote generator** - Extracts concise 1-3 sentence passages, not long paragraphs
- **English-first output** - Translations via Google Translate, with optional Chinese metadata
- **19 classical texts** - Analects, Dao De Jing, Mengzi, Mozi, Art of War, and more
- **Duplicate tracking** - SQLite-backed history so you never see the same quote twice
- **Batch export** - Generate dozens of quotes to a file in one command
- **Multiple formats** - Plain text, JSON, or full annotated output
- **Cross-platform** - Works on macOS, Linux, and Windows

## Installation

### pip (recommended)

```bash
pip install git+https://github.com/3D3Q3/chtext.git
```

After installation the `chtext` command is available globally.

### From source

```bash
git clone https://github.com/3D3Q3/chtext.git
cd chtext
pip install .
```

### Without installing

```bash
git clone https://github.com/3D3Q3/chtext.git
cd chtext
pip install requests deep-translator
python -m chtext generate
```

## Quick Start

```bash
# Get a short English quote from a random classical text
chtext generate

# Quote from a specific book
chtext generate --book dao-de-jing

# Include the original Chinese text
chtext generate --with-chinese

# Generate 20 quotes and save to a file
chtext generate --count 20 --output quotes.txt

# Output as JSON
chtext generate --format json

# See all available books
chtext list
```

## Commands

| Command | Description |
|---------|-------------|
| `generate` | Generate short English quotes (the main feature) |
| `random` | Get a random full paragraph with translation |
| `unique` | Get a full paragraph you haven't seen before |
| `batch` | Export multiple full paragraphs to a file |
| `list` | List all available books |
| `search` | Search texts by Chinese keyword |
| `browse` | Explore a book's chapter structure |
| `download` | Download a complete text to a file |
| `stats` | View your quote history |
| `status` | Check API connection and rate limits |
| `config` | Manage API key and preferences |

### generate

The primary command. Fetches passages from the ctext.org API, splits long paragraphs into individual sentences, filters for short quotable passages, and translates them to English.

```bash
# Single quote
chtext generate

# From a specific book
chtext generate --book analects

# Batch to file
chtext generate --count 50 --output my_quotes.txt

# With Chinese text shown below each translation
chtext generate --count 10 --with-chinese

# JSON output (useful for programmatic consumption)
chtext generate --format json
```

### config

```bash
# View current settings
chtext config --show

# Set an API key to unlock all books
chtext config --set-apikey YOUR_KEY

# Use simplified Chinese characters
chtext config --set-remap gb

# Set default book for random/generate
chtext config --set-default-book analects
```

## Available Books

Five classical texts are available without an API key:

| Key | Text |
|-----|------|
| `analects` | The Analects (論語) |
| `mengzi` | Mengzi (孟子) |
| `dao-de-jing` | Dao De Jing (道德經) |
| `mozi` | Mozi (墨子) |
| `book-of-poetry` | Book of Poetry (詩經) |

With a [ctext.org API key](https://ctext.org/tools/subscribe), 14 additional texts are unlocked including Zhuangzi, Art of War, Han Feizi, Book of Rites, Records of the Grand Historian, and more. Run `chtext list` for the full catalog.

## API Key

The tool works immediately without any API key. The free tier gives access to five major texts, which contain thousands of quotable passages.

For access to the full library:

1. Visit [ctext.org/tools/subscribe](https://ctext.org/tools/subscribe)
2. Register for an API key
3. Set it: `chtext config --set-apikey YOUR_KEY`

## How It Works

1. Fetches text data from the [ctext.org API](https://ctext.org/tools/api)
2. Navigates book structure (books → chapters → paragraphs)
3. Splits long paragraphs into sentences using Chinese punctuation boundaries (。！？)
4. Filters for short, quotable passages (under ~80 characters)
5. Translates to English via Google Translate
6. Tracks seen quotes in a local SQLite database to avoid duplicates

## Requirements

- Python 3.8+
- Internet connection (for the ctext.org API and Google Translate)

## License

[MIT](LICENSE)

## Acknowledgments

- [Chinese Text Project (ctext.org)](https://ctext.org) - The comprehensive database of classical Chinese texts that makes this tool possible
- Created by Donald Sturgeon, the Chinese Text Project is a freely accessible digital library of pre-modern Chinese texts
