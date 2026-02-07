# Ctext.org Chinese Classics CLI v3.0

A professional command-line tool for retrieving classical Chinese texts from the Chinese Text Project (ctext.org) with English translations.

## Features

- 🎲 **Random quotes** from classical Chinese texts
- 🔖 **Unique quotes** tracking (never see the same quote twice)
- 🔍 **Search** texts by content
- 📚 **Browse** book structure and chapters
- ⬇️ **Download** full texts to file
- 📊 **Statistics** on your reading history
- ⚙️ **Configuration** for API key and preferences
- 🌐 **Automatic translation** via Google Translate

## Installation

```bash
# Clone or copy the project
cd CHTEXT

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: .\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

```bash
# Get a random quote with translation
python main.py random

# Get a quote from a specific book
python main.py random --book dao-de-jing

# Get a unique quote (tracks seen quotes)
python main.py unique

# List all available books
python main.py list
```

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `random` | Get a random quote from any book |
| `unique` | Get a quote you haven't seen before |
| `batch` | Generate multiple unique quotes to a file |
| `list` | List all available books by category |
| `stats` | Show your quote history statistics |

### New Commands (v3.0)

| Command | Description |
|---------|-------------|
| `search` | Search for passages containing specific text |
| `browse` | Explore book structure and chapters |
| `download` | Download full text of a book to file |
| `status` | Show API status and rate limit info |
| `config` | Manage API key and settings |

## Usage Examples

### Random Quotes

```bash
# Random quote from any book
python main.py random

# From a specific book, no translation
python main.py random --book analects --no-translate

# Output as JSON
python main.py random --format json
```

### Search

```bash
# Search for "仁" (benevolence) in all texts
python main.py search --query "仁"

# Search within the Analects only
python main.py search --query "君子" --book analects

# Show more results
python main.py search --query "道" --limit 20
```

### Browse

```bash
# See chapter structure of a book
python main.py browse analects

# See more chapters
python main.py browse shijing --limit 50
```

### Download

```bash
# Download full text (as paragraphs)
python main.py download dao-de-jing

# Download as continuous string
python main.py download analects --format string

# Specify output file
python main.py download mengzi --output mengzi_full.txt
```

### Batch Generation

```bash
# Generate 10 unique quotes
python main.py batch --count 10

# From specific book, as JSON
python main.py batch --count 5 --book zhuangzi --format json
```

### Configuration

```bash
# Show current config
python main.py config --show

# Set API key (when you have one)
python main.py config --set-apikey YOUR_API_KEY

# Set language (en/zh)
python main.py config --set-language zh

# Use simplified Chinese
python main.py config --set-remap gb
```

## Available Books

The CLI includes 24+ classical Chinese texts organized by category:

- **Confucian Classics**: Analects, Mengzi, Xunzi, Great Learning, Doctrine of the Mean
- **Daoist Texts**: Dao De Jing, Zhuangzi, Liezi
- **Legalist & Military**: Han Feizi, Art of War, Book of Lord Shang
- **Mohist**: Mozi
- **Five Classics**: I Ching, Book of Odes, Book of Rites, Zuo Zhuan, Book of Documents
- **Historical**: Records of Grand Historian, Strategies of Warring States
- **Other Philosophy**: Guanzi, Yanzi Chunqiu, Lüshi Chunqiu, Huainanzi

Run `python main.py list` to see the full categorized list.

## API Key

The app works without an API key but with rate limitations. For extended access:

1. Create an account at [ctext.org](https://ctext.org)
2. For API keys, see [ctext.org/tools/subscribe](https://ctext.org/tools/subscribe)
3. Set your key: `python main.py config --set-apikey YOUR_KEY`

## Dependencies

- `ctext` - Official Chinese Text Project Python library
- `requests` - HTTP requests  
- `deep-translator` - Google Translate wrapper

## Resources

- [ctext.org](https://ctext.org) - Chinese Text Project
- [API Documentation](https://ctext.org/tools/api)
- [Digital Sinology Tutorials](https://digitalsinology.org/classical-chinese-digital-humanities/)

## License

MIT License - Educational and research use encouraged.
