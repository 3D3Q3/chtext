#!/usr/bin/env python3
"""
Ctext.org Chinese Classics Quote CLI v3.0

A professional command-line tool for retrieving classical Chinese texts
from the Chinese Text Project using the official ctext Python library.

Features:
- Random/unique quote retrieval with translation
- Text search functionality  
- Book/chapter browsing
- Download texts to file
- API status and configuration
"""

import argparse
import hashlib
import io
import json
import os
import random
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional, Dict, List, Any

# Fix Windows console encoding for Chinese characters
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import re

import requests
from deep_translator import GoogleTranslator

# --- Direct API client for ctext.org (replaces broken 'ctext' package) ---

class CTextAPI:
    """Direct HTTP client for the Chinese Text Project API (api.ctext.org).
    Replaces the 'ctext' PyPI package which has build issues."""

    def __init__(self):
        self.base = "https://api.ctext.org"
        self.session = requests.Session()
        self.apikey = ""
        self.language = ""
        self.remap = ""

    def _build_params(self):
        params = {}
        if self.apikey:
            params["apikey"] = self.apikey
        if self.language:
            params["if"] = self.language
        if self.remap:
            params["remap"] = self.remap
        return params

    def _call(self, endpoint, extra_params=None):
        params = self._build_params()
        if extra_params:
            params.update(extra_params)
        resp = self.session.get(f"{self.base}/{endpoint}", params=params, timeout=30)
        if not resp.text.strip():
            raise CtextAPIError("Empty response from API (possible rate limit)")
        data = resp.json()
        if "error" in data:
            code = data["error"].get("code", "")
            desc = data["error"].get("description", "")
            if "authentication" in code.lower() or "authentication" in desc.lower():
                raise CtextAuthError(f"This text requires an API key. Get one at https://ctext.org/tools/subscribe")
            raise CtextAPIError(f"API Error [{code}]: {desc}")
        return data

    def gettext(self, urn):
        return self._call("gettext", {"urn": urn})

    def searchtexts(self, title):
        return self._call("searchtexts", {"title": title})

    def getstatus(self):
        return self._call("getstatus")

    def gettextinfo(self, urn):
        return self._call("gettextinfo", {"urn": urn})

    def gettextasstring(self, urn):
        data = self.gettext(urn)
        result = ""
        if "subsections" in data:
            for sub in data["subsections"]:
                result += self.gettextasstring(sub)
        if "fulltext" in data:
            for para in data["fulltext"]:
                result += para + "\n\n"
        return result

    def gettextasparagraphlist(self, urn):
        text = self.gettextasstring(urn)
        parts = re.split(r"\n+", text)
        if parts and parts[-1] == "":
            parts.pop()
        return parts

    def setapikey(self, key):
        self.apikey = key

    def setlanguage(self, lang):
        self.language = lang

    def setremap(self, remap):
        self.remap = remap


# Shared API instance (replaces the ctext module-level globals)
ctapi = CTextAPI()


# --- Configuration & Constants ---
DB_FILE = "seen_ids.sqlite"
CONFIG_FILE = Path.home() / ".ctext_config.json"
REQUEST_DELAY = 1.0  # Seconds between API requests to respect rate limits
MAX_RETRIES = 15     # Maximum retries for unique quote finding

# Books available without an API key (free tier)
FREE_BOOKS = {
    "analects": ("ctp:analects", "The Analects (論語)"),
    "mengzi": ("ctp:mengzi", "Mengzi (孟子)"),
    "dao-de-jing": ("ctp:dao-de-jing", "Dao De Jing (道德經)"),
    "mozi": ("ctp:mozi", "Mozi (墨子)"),
    "book-of-poetry": ("ctp:book-of-poetry", "Book of Poetry / Shijing (詩經)"),
}

# Books that require a ctext.org API key
AUTH_BOOKS = {
    "xunzi": ("ctp:xunzi", "Xunzi (荀子)"),
    "zhuangzi": ("ctp:zhuangzi", "Zhuangzi (莊子)"),
    "liezi": ("ctp:liezi", "Liezi (列子)"),
    "hanfeizi": ("ctp:hanfeizi", "Han Feizi (韓非子)"),
    "art-of-war": ("ctp:art-of-war", "Art of War (孫子兵法)"),
    "shang-jun-shu": ("ctp:shang-jun-shu", "Book of Lord Shang (商君書)"),
    "liji": ("ctp:liji", "Book of Rites (禮記)"),
    "book-of-changes": ("ctp:book-of-changes", "I Ching / Book of Changes (易經)"),
    "chun-qiu-zuo-zhuan": ("ctp:chun-qiu-zuo-zhuan", "Zuo Zhuan (左傳)"),
    "shiji": ("ctp:shiji", "Records of the Grand Historian (史記)"),
    "zhan-guo-ce": ("ctp:zhan-guo-ce", "Strategies of the Warring States (戰國策)"),
    "guanzi": ("ctp:guanzi", "Guanzi (管子)"),
    "lv-shi-chun-qiu": ("ctp:lv-shi-chun-qiu", "Lüshi Chunqiu (呂氏春秋)"),
    "huainanzi": ("ctp:huainanzi", "Huainanzi (淮南子)"),
}

# Combined dict for CLI compatibility (--book accepts any known book)
AVAILABLE_BOOKS = {**FREE_BOOKS, **AUTH_BOOKS}


class CtextAPIError(Exception):
    """Custom exception for API errors."""
    pass


class CtextAuthError(CtextAPIError):
    """Raised when a text requires authentication."""
    pass


class Config:
    """Configuration manager for persistent settings."""
    
    def __init__(self, config_path: Path = CONFIG_FILE):
        self.config_path = config_path
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load configuration from file.""" 
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "api_key": None,
            "default_book": None,
            "language": "en",
            "remap": None,  # 'gb' for simplified Chinese
            "output_format": "full"
        }
    
    def save(self):
        """Save configuration to file."""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)
    
    def get(self, key: str, default=None):
        return self.data.get(key, default)
    
    def set(self, key: str, value):
        self.data[key] = value
        self.save()
    
    def apply_to_ctext(self):
        """Apply configuration to the ctext API client."""
        if self.data.get("api_key"):
            ctapi.setapikey(self.data["api_key"])
        if self.data.get("language"):
            ctapi.setlanguage(self.data["language"])
        if self.data.get("remap"):
            ctapi.setremap(self.data["remap"])


class CtextLibWrapper:
    """Wrapper for the official ctext Python library with enhanced functionality."""
    
    def __init__(self, config: Config, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.config.apply_to_ctext()

    def _log(self, message: str):
        """Print debug messages if verbose mode is enabled."""
        if self.verbose:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def get_text(self, urn: str) -> Dict:
        """Fetch text data for a given URN."""
        self._log(f"Fetching text for URN: {urn}")
        time.sleep(REQUEST_DELAY)
        try:
            result = ctapi.gettext(urn)
            return result
        except (CtextAuthError, CtextAPIError):
            raise
        except Exception as e:
            raise CtextAPIError(str(e))

    def get_text_as_paragraphs(self, urn: str) -> List[str]:
        """Get full text as a list of paragraphs."""
        self._log(f"Fetching paragraphs for URN: {urn}")
        time.sleep(REQUEST_DELAY)
        try:
            result = ctapi.gettextasparagraphlist(urn)
            return result if result else []
        except Exception as e:
            raise CtextAPIError(f"Failed to get paragraphs: {e}")

    def get_text_as_string(self, urn: str) -> str:
        """Get full text as a single string."""
        self._log(f"Fetching full text for URN: {urn}")
        time.sleep(REQUEST_DELAY)
        try:
            result = ctapi.gettextasstring(urn)
            return result if result else ""
        except Exception as e:
            raise CtextAPIError(f"Failed to get text: {e}")

    def get_status(self) -> Dict:
        """Get API status including rate limit info."""
        self._log("Fetching API status")
        try:
            result = ctapi.getstatus()
            return result if result else {}
        except Exception as e:
            raise CtextAPIError(f"Failed to get status: {e}")

    def search_texts(self, query: str, urn: Optional[str] = None) -> List[Dict]:
        """Search for texts containing the query."""
        self._log(f"Searching for: {query} in {urn or 'all texts'}")
        time.sleep(REQUEST_DELAY)
        try:
            # ctext API searchtexts only takes a title/query param
            result = ctapi.searchtexts(query)
            return result if result else []
        except Exception as e:
            raise CtextAPIError(f"Search failed: {e}")

    def get_available_books(self) -> Dict[str, tuple]:
        """Return the dictionary of available books."""
        return AVAILABLE_BOOKS


class TranslatorWrapper:
    """Wrapper for translation services."""
    
    def __init__(self, verbose: bool = False):
        self.translator = GoogleTranslator(source='zh-CN', target='en')
        self.verbose = verbose

    def translate(self, text: str) -> str:
        """Translate Chinese text to English."""
        if not text or not text.strip():
            return "[Empty text]"
        try:
            result = self.translator.translate(text)
            return result if result else "[Translation unavailable]"
        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Translation error: {e}", file=sys.stderr)
            return f"[Translation Error: {type(e).__name__}]"


class StateTracker:
    """SQLite-based state tracking for seen quotes."""
    
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS seen_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unique_id TEXT UNIQUE NOT NULL,
                    book_urn TEXT,
                    chapter_urn TEXT,
                    text_preview TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def is_seen(self, unique_id: str) -> bool:
        """Check if a quote has been seen before."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM seen_quotes WHERE unique_id = ?", 
                (unique_id,)
            )
            return cursor.fetchone() is not None

    def mark_seen(self, unique_id: str, book_urn: str = "", chapter_urn: str = "", text_preview: str = ""):
        """Mark a quote as seen."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    "INSERT INTO seen_quotes (unique_id, book_urn, chapter_urn, text_preview) VALUES (?, ?, ?, ?)",
                    (unique_id, book_urn, chapter_urn, text_preview[:100])
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # Already seen

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about seen quotes."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM seen_quotes")
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT book_urn, COUNT(*) as count FROM seen_quotes GROUP BY book_urn ORDER BY count DESC"
            )
            by_book = cursor.fetchall()
            
            cursor = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM seen_quotes"
            )
            date_range = cursor.fetchone()
            
            return {
                "total": total,
                "by_book": by_book,
                "first_seen": date_range[0],
                "last_seen": date_range[1]
            }

    def reset(self):
        """Clear all seen quotes."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM seen_quotes")
            conn.commit()


class QuoteFetcher:
    """Main logic for fetching quotes using the ctext library."""
    
    def __init__(self, config: Config, verbose: bool = False):
        self.api = CtextLibWrapper(config, verbose=verbose)
        self.translator = TranslatorWrapper(verbose=verbose)
        self.state = StateTracker()
        self.verbose = verbose

    def _log(self, message: str):
        """Print debug messages if verbose mode is enabled."""
        if self.verbose:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def _get_book_urn(self, book_key: Optional[str], free_only: bool = False) -> str:
        """Get the URN for a book by key, or pick a random one."""
        if book_key:
            if book_key not in AVAILABLE_BOOKS:
                available = ", ".join(AVAILABLE_BOOKS.keys())
                raise ValueError(f"Unknown book '{book_key}'. Available: {available}")
            return AVAILABLE_BOOKS[book_key][0]
        pool = FREE_BOOKS if free_only else AVAILABLE_BOOKS
        return random.choice(list(pool.values()))[0]

    def _generate_unique_id(self, chapter_urn: str, paragraph_index: int, text: str) -> str:
        """Generate a stable unique ID for a paragraph."""
        content = f"{chapter_urn}:{paragraph_index}:{hashlib.md5(text.encode()).hexdigest()[:8]}"
        return content

    def fetch_quote(self, book_key: Optional[str] = None, unique: bool = False) -> Optional[Dict]:
        """
        Fetch a quote from a book.
        
        Args:
            book_key: Optional specific book to fetch from
            unique: If True, only return quotes not seen before
        
        Returns:
            Dictionary with quote data or None if no quote found
        """
        max_attempts = MAX_RETRIES if unique else 3
        
        for attempt in range(max_attempts):
            try:
                book_urn = self._get_book_urn(book_key)
                self._log(f"Attempt {attempt + 1}: Fetching from {book_urn}")
                
                # Fetch the book/chapter data
                data = self.api.get_text(book_urn)
                
                # Handle books that have subsections (like Analects)
                if isinstance(data, dict) and "subsections" in data and data["subsections"]:
                    chapter_urn = random.choice(data["subsections"])
                    self._log(f"Selected chapter: {chapter_urn}")
                    data = self.api.get_text(chapter_urn)
                elif isinstance(data, dict):
                    chapter_urn = book_urn
                else:
                    chapter_urn = book_urn
                
                # Now get the fulltext
                if not isinstance(data, dict) or "fulltext" not in data or not data["fulltext"]:
                    self._log(f"No fulltext in response for {chapter_urn}")
                    continue
                
                fulltext = data["fulltext"]
                title = data.get("title", "Unknown")
                
                # fulltext is a list of strings (paragraphs)
                # Filter out empty ones
                valid_paragraphs = []
                for i, p in enumerate(fulltext):
                    if isinstance(p, str) and p.strip():
                        valid_paragraphs.append((i, p.strip()))
                    elif isinstance(p, dict) and p.get("text", "").strip():
                        valid_paragraphs.append((i, p["text"].strip()))
                
                if not valid_paragraphs:
                    self._log(f"No valid paragraphs in {chapter_urn}")
                    continue
                
                # Pick a random paragraph
                para_index, quote_text = random.choice(valid_paragraphs)
                unique_id = self._generate_unique_id(chapter_urn, para_index, quote_text)
                
                # Check uniqueness if required
                if unique and self.state.is_seen(unique_id):
                    self._log(f"Quote already seen: {unique_id}")
                    continue
                
                # Found a valid quote!
                quote = {
                    "text": quote_text,
                    "book_urn": book_urn,
                    "chapter_urn": chapter_urn,
                    "chapter_title": title,
                    "paragraph_index": para_index,
                    "unique_id": unique_id,
                }
                
                if unique:
                    self.state.mark_seen(unique_id, book_urn, chapter_urn, quote_text)
                
                return quote
                
            except CtextAPIError as e:
                print(f"API Error: {e}", file=sys.stderr)
                if attempt < max_attempts - 1:
                    self._log("Retrying...")
                    continue
                return None
            except Exception as e:
                self._log(f"Unexpected error: {e}")
                if attempt < max_attempts - 1:
                    continue
                return None
        
        return None

    def format_quote(self, quote: Dict, include_translation: bool = True, format_style: str = "full") -> str:
        """Format a quote for display."""
        if format_style == "json":
            output = quote.copy()
            if include_translation:
                output["translation"] = self.translator.translate(quote["text"])
            return json.dumps(output, ensure_ascii=False, indent=2)
        
        if format_style == "minimal":
            return quote["text"]
        
        lines = []
        
        if format_style == "full":
            lines.append("=" * 50)
            
            # Get book display name
            book_name = quote["book_urn"]
            for key, (urn, display) in AVAILABLE_BOOKS.items():
                if urn == quote["book_urn"]:
                    book_name = display
                    break
            
            lines.append(f"📚 {book_name}")
            lines.append(f"📖 Chapter: {quote['chapter_title']}")
            lines.append("-" * 50)
        
        lines.append(f"「{quote['text']}」")
        
        if include_translation:
            if format_style == "full":
                lines.append("-" * 50)
            translation = self.translator.translate(quote["text"])
            lines.append(f"Translation: {translation}")
        
        if format_style == "full":
            lines.append("=" * 50)
        
        return "\n".join(lines)

    def fetch_short_quote(self, book_key: Optional[str] = None, unique: bool = True,
                          max_chars: int = 80) -> Optional[Dict]:
        """Fetch a short quote (1-3 sentences) from a book.

        Splits long paragraphs into individual sentences and filters by length
        so only concise, quotable passages are returned.
        """
        max_attempts = MAX_RETRIES if unique else 5

        for attempt in range(max_attempts):
            try:
                book_urn = self._get_book_urn(book_key, free_only=(book_key is None))
                self._log(f"Short-quote attempt {attempt + 1}: {book_urn}")

                data = self.api.get_text(book_urn)

                # Navigate into subsections if the book has chapters
                if isinstance(data, dict) and "subsections" in data and data["subsections"]:
                    chapter_urn = random.choice(data["subsections"])
                    self._log(f"Selected chapter: {chapter_urn}")
                    data = self.api.get_text(chapter_urn)
                elif isinstance(data, dict):
                    chapter_urn = book_urn
                else:
                    chapter_urn = book_urn

                if not isinstance(data, dict) or "fulltext" not in data or not data["fulltext"]:
                    continue

                title = data.get("title", "Unknown")
                candidates = _extract_short_segments(data["fulltext"], max_chars)

                if not candidates:
                    self._log("No short segments found in this chapter")
                    continue

                random.shuffle(candidates)

                for para_idx, segment in candidates:
                    uid = self._generate_unique_id(chapter_urn, para_idx, segment)
                    if unique and self.state.is_seen(uid):
                        continue

                    # Translate to English
                    translation = self.translator.translate(segment)

                    quote = {
                        "text": segment,
                        "translation": translation,
                        "book_urn": book_urn,
                        "chapter_urn": chapter_urn,
                        "chapter_title": title,
                        "paragraph_index": para_idx,
                        "unique_id": uid,
                    }
                    if unique:
                        self.state.mark_seen(uid, book_urn, chapter_urn, segment)
                    return quote

            except CtextAuthError as e:
                # Don't retry auth errors - the book needs an API key
                print(f"Auth required: {e}", file=sys.stderr)
                return None
            except CtextAPIError as e:
                self._log(f"API error: {e}")
                if attempt < max_attempts - 1:
                    continue
                return None
            except Exception as e:
                self._log(f"Unexpected error: {e}")
                if attempt < max_attempts - 1:
                    continue
                return None

        return None


def _extract_short_segments(fulltext: List, max_chars: int = 80) -> List[tuple]:
    """Split paragraphs into short, quotable sentence-level segments.

    Returns list of (paragraph_index, segment_text) tuples.
    Chinese sentence-ending punctuation: 。！？
    """
    # Regex: split AFTER sentence-ending punctuation (keep the punct with the sentence)
    splitter = re.compile(r"(?<=[。！？])")
    results = []

    for i, para in enumerate(fulltext):
        text = para.strip() if isinstance(para, str) else ""
        if isinstance(para, dict):
            text = para.get("text", "").strip()
        if not text or len(text) < 4:
            continue

        # If the whole paragraph is already short, take it directly
        if len(text) <= max_chars:
            results.append((i, text))
            continue

        # Split into individual sentences
        sentences = [s.strip() for s in splitter.split(text) if s.strip()]
        # Filter out tiny fragments (closing brackets etc.)
        sentences = [s for s in sentences if len(s) >= 4]

        # Individual short sentences
        for s in sentences:
            if len(s) <= max_chars:
                results.append((i, s))

        # Consecutive pairs of sentences (for 2-sentence quotes)
        for j in range(len(sentences) - 1):
            pair = sentences[j] + sentences[j + 1]
            if len(pair) <= max_chars:
                results.append((i, pair))

    return results


def _format_english_quote(quote: Dict, with_chinese: bool = False) -> str:
    """Format a quote with English translation as the primary text."""
    # Find book display name
    book_name = quote["book_urn"]
    for _key, (urn, display) in AVAILABLE_BOOKS.items():
        if urn == quote["book_urn"]:
            book_name = display
            break

    lines = [f'"{quote["translation"]}"']
    lines.append(f"  -- {book_name}, {quote['chapter_title']}")
    if with_chinese:
        lines.append(f"     {quote['text']}")
    return "\n".join(lines)


# --- CLI Commands ---

def cmd_random(args, fetcher: QuoteFetcher):
    """Handle the 'random' command."""
    quote = fetcher.fetch_quote(book_key=args.book, unique=False)
    
    if not quote:
        print("Error: Could not retrieve a quote. Please try again.", file=sys.stderr)
        return 1
    
    print(fetcher.format_quote(
        quote, 
        include_translation=not args.no_translate,
        format_style=args.format
    ))
    return 0


def cmd_unique(args, fetcher: QuoteFetcher):
    """Handle the 'unique' command."""
    quote = fetcher.fetch_quote(book_key=args.book, unique=True)
    
    if not quote:
        stats = fetcher.state.get_stats()
        print(f"Error: Could not find a unique quote after {MAX_RETRIES} attempts.", file=sys.stderr)
        print(f"You have seen {stats['total']} quotes. Consider using 'stats --reset' to clear history.", file=sys.stderr)
        return 1
    
    print(fetcher.format_quote(
        quote,
        include_translation=not args.no_translate,
        format_style=args.format
    ))
    return 0


def cmd_batch(args, fetcher: QuoteFetcher):
    """Handle the 'batch' command."""
    output_file = args.output or f"quotes_{int(time.time())}.txt"
    count = args.count
    
    print(f"Generating {count} unique quotes...")
    print(f"Output file: {output_file}")
    print()
    
    success_count = 0
    quotes_data = []
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for i in range(count):
            quote = fetcher.fetch_quote(book_key=args.book, unique=True)
            
            if quote:
                if args.format == "json":
                    quote_with_trans = quote.copy()
                    if not args.no_translate:
                        quote_with_trans["translation"] = fetcher.translator.translate(quote["text"])
                    quotes_data.append(quote_with_trans)
                else:
                    formatted = fetcher.format_quote(
                        quote,
                        include_translation=not args.no_translate,
                        format_style="full"
                    )
                    f.write(formatted + "\n\n")
                success_count += 1
                print(f"  [{success_count}/{count}] ✓ Saved quote from {quote['chapter_title']}")
            else:
                print(f"  [{i+1}/{count}] ✗ Could not find unique quote")
        
        # Write JSON at end if format is json
        if args.format == "json":
            f.write(json.dumps(quotes_data, ensure_ascii=False, indent=2))
    
    print()
    print(f"Done! Saved {success_count}/{count} quotes to {output_file}")
    return 0 if success_count > 0 else 1


def cmd_list(args, fetcher: QuoteFetcher):
    """Handle the 'list' command."""
    print("Available Books:")
    print("=" * 60)

    print("\n  FREE (no API key needed):")
    print("-" * 40)
    for key, (urn, display) in FREE_BOOKS.items():
        print(f"  {key:22} {display}")

    print("\n  REQUIRES API KEY (ctext.org/tools/subscribe):")
    print("-" * 40)
    for key, (urn, display) in AUTH_BOOKS.items():
        print(f"  {key:22} {display}")

    print("\n" + "=" * 60)
    print(f"\nUse --book <key> to select a specific book.")
    print(f"Example: python main.py random --book analects")
    return 0


def cmd_stats(args, fetcher: QuoteFetcher):
    """Handle the 'stats' command."""
    if args.reset:
        fetcher.state.reset()
        print("✓ Quote history has been reset.")
        return 0
    
    stats = fetcher.state.get_stats()
    
    print("Quote Statistics")
    print("=" * 40)
    print(f"Total quotes seen: {stats['total']}")
    
    if stats['first_seen']:
        print(f"First seen: {stats['first_seen']}")
        print(f"Last seen: {stats['last_seen']}")
    
    if stats['by_book']:
        print("\nBy Book:")
        print("-" * 40)
        for book_urn, count in stats['by_book']:
            # Find display name
            display = book_urn
            for key, (urn, name) in AVAILABLE_BOOKS.items():
                if urn == book_urn:
                    display = name
                    break
            print(f"  {display}: {count}")
    
    print("=" * 40)
    return 0


def cmd_search(args, fetcher: QuoteFetcher, config: Config):
    """Handle the 'search' command."""
    query = args.query
    book_key = args.book
    
    print(f"Searching for: '{query}'")
    if book_key:
        if book_key not in AVAILABLE_BOOKS:
            print(f"Error: Unknown book '{book_key}'", file=sys.stderr)
            return 1
        urn = AVAILABLE_BOOKS[book_key][0]
        print(f"In book: {AVAILABLE_BOOKS[book_key][1]}")
    else:
        urn = None
        print("In: all texts")
    print()
    
    try:
        results = fetcher.api.search_texts(query, urn)
        
        if not results:
            print("No results found.")
            return 0
        
        if args.format == "json":
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(f"Found {len(results)} result(s):")
            print("-" * 50)
            for i, result in enumerate(results[:args.limit], 1):
                if isinstance(result, dict):
                    text = result.get("text", result.get("passage", str(result)))
                    title = result.get("title", "")
                    urn = result.get("urn", "")
                    print(f"\n[{i}] {title}")
                    print(f"    URN: {urn}")
                    print(f"    「{text[:200]}{'...' if len(text) > 200 else ''}」")
                else:
                    print(f"\n[{i}] {result}")
        
        return 0
    except CtextAPIError as e:
        print(f"Search error: {e}", file=sys.stderr)
        return 1


def cmd_browse(args, fetcher: QuoteFetcher):
    """Handle the 'browse' command."""
    book_key = args.book
    
    if book_key not in AVAILABLE_BOOKS:
        print(f"Error: Unknown book '{book_key}'", file=sys.stderr)
        print(f"Use 'list' command to see available books.")
        return 1
    
    urn, display_name = AVAILABLE_BOOKS[book_key]
    
    print(f"📚 {display_name}")
    print(f"   URN: {urn}")
    print("=" * 50)
    
    try:
        data = fetcher.api.get_text(urn)
        
        if not isinstance(data, dict):
            print("Error: Unexpected response format", file=sys.stderr)
            return 1
        
        if "subsections" in data and data["subsections"]:
            print(f"\n📖 Chapters ({len(data['subsections'])}):")
            print("-" * 40)
            for i, sub_urn in enumerate(data["subsections"][:args.limit], 1):
                # Try to get chapter title
                try:
                    sub_data = fetcher.api.get_text(sub_urn)
                    title = sub_data.get("title", sub_urn) if isinstance(sub_data, dict) else sub_urn
                except:
                    title = sub_urn
                print(f"  {i:3}. {title}")
                print(f"       URN: {sub_urn}")
            
            if len(data["subsections"]) > args.limit:
                print(f"\n  ... and {len(data['subsections']) - args.limit} more chapters")
                print(f"  Use --limit to show more")
        
        elif "fulltext" in data and data["fulltext"]:
            print(f"\n📝 Full Text ({len(data['fulltext'])} paragraphs):")
            print("-" * 40)
            for i, para in enumerate(data["fulltext"][:5], 1):
                text = para if isinstance(para, str) else para.get("text", "")
                preview = text[:80] + "..." if len(text) > 80 else text
                print(f"  {i}. 「{preview}」")
            
            if len(data["fulltext"]) > 5:
                print(f"\n  ... and {len(data['fulltext']) - 5} more paragraphs")
        
        else:
            print("\nNo content available (may require authentication)")
            print("Tip: Set an API key with 'config --set-apikey YOUR_KEY'")
        
        return 0
        
    except CtextAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_download(args, fetcher: QuoteFetcher):
    """Handle the 'download' command."""
    book_key = args.book
    
    if book_key not in AVAILABLE_BOOKS:
        print(f"Error: Unknown book '{book_key}'", file=sys.stderr)
        return 1
    
    urn, display_name = AVAILABLE_BOOKS[book_key]
    output_file = args.output or f"{book_key}_{int(time.time())}.txt"
    
    print(f"Downloading: {display_name}")
    print(f"Output file: {output_file}")
    print()
    
    try:
        if args.format == "string":
            text = fetcher.api.get_text_as_string(urn)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# {display_name}\n")
                f.write(f"# URN: {urn}\n")
                f.write(f"# Downloaded: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(text)
            print(f"✓ Saved as continuous text")
        else:
            paragraphs = fetcher.api.get_text_as_paragraphs(urn)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# {display_name}\n")
                f.write(f"# URN: {urn}\n")
                f.write(f"# Downloaded: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Paragraphs: {len(paragraphs)}\n\n")
                for i, para in enumerate(paragraphs, 1):
                    f.write(f"[{i}] {para}\n\n")
            print(f"✓ Saved {len(paragraphs)} paragraphs")
        
        print(f"✓ Done: {output_file}")
        return 0
        
    except CtextAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_status(args, fetcher: QuoteFetcher, config: Config):
    """Handle the 'status' command."""
    print("API Status")
    print("=" * 40)
    
    # Show current config
    api_key = config.get("api_key")
    print(f"API Key: {'[SET]' if api_key else '[NOT SET]'}")
    print(f"Language: {config.get('language', 'en')}")
    print(f"Remap: {config.get('remap') or 'None (Traditional Chinese)'}")
    print()
    
    try:
        status = fetcher.api.get_status()
        
        if isinstance(status, dict):
            print("Server Status:")
            print("-" * 40)
            for key, value in status.items():
                print(f"  {key}: {value}")
        else:
            print(f"Status: {status}")
        
    except CtextAPIError as e:
        print(f"Could not fetch status: {e}", file=sys.stderr)
        print("\nNote: Some features require an API key or account.")
        print("Visit https://ctext.org/tools/subscribe for more info.")
    
    print("=" * 40)
    return 0


def cmd_config(args, config: Config):
    """Handle the 'config' command."""
    if args.show:
        print("Current Configuration")
        print("=" * 40)
        print(f"Config file: {config.config_path}")
        print("-" * 40)
        for key, value in config.data.items():
            display_value = "[SET]" if key == "api_key" and value else value
            print(f"  {key}: {display_value}")
        print("=" * 40)
        return 0
    
    if args.set_apikey is not None:
        key = args.set_apikey.strip()
        if key.lower() == "none" or key == "":
            config.set("api_key", None)
            print("✓ API key cleared")
        else:
            config.set("api_key", key)
            print(f"✓ API key set")
        return 0
    
    if args.set_language:
        config.set("language", args.set_language)
        print(f"✓ Language set to: {args.set_language}")
        return 0
    
    if args.set_remap:
        if args.set_remap.lower() == "none":
            config.set("remap", None)
            print("✓ Remap disabled (Traditional Chinese)")
        else:
            config.set("remap", args.set_remap)
            print(f"✓ Remap set to: {args.set_remap}")
        return 0
    
    if args.set_default_book:
        if args.set_default_book.lower() == "none":
            config.set("default_book", None)
            print("✓ Default book cleared")
        elif args.set_default_book in AVAILABLE_BOOKS:
            config.set("default_book", args.set_default_book)
            print(f"✓ Default book set to: {args.set_default_book}")
        else:
            print(f"Error: Unknown book '{args.set_default_book}'", file=sys.stderr)
            return 1
        return 0
    
    # No specific command - show help
    print("Use 'config --show' to view current settings")
    print("Use 'config --set-apikey KEY' to set API key")
    print("Use 'config --set-language LANG' to set language (en/zh)")
    print("Use 'config --set-remap MODE' to set character mapping (gb/none)")
    return 0


def cmd_generate(args, fetcher: QuoteFetcher):
    """Handle the 'generate' command - produce short English quotes."""
    count = getattr(args, "count", 1)
    book_key = getattr(args, "book", None)
    with_chinese = getattr(args, "with_chinese", False)
    output_file = getattr(args, "output", None)
    fmt = getattr(args, "format", "text")

    quotes_collected = []

    if count == 1 and not output_file:
        # Single quote mode - print directly
        quote = fetcher.fetch_short_quote(book_key=book_key, unique=True)
        if not quote:
            print("Could not find a short quote. Try again or specify a different --book.", file=sys.stderr)
            return 1
        if fmt == "json":
            print(json.dumps(quote, ensure_ascii=False, indent=2))
        else:
            print(_format_english_quote(quote, with_chinese=with_chinese))
        return 0

    # Multi-quote / file mode
    target = output_file or f"english_quotes_{int(time.time())}.txt"
    print(f"Generating {count} short English quotes...")
    if output_file:
        print(f"Output: {target}")
    print()

    for i in range(count):
        quote = fetcher.fetch_short_quote(book_key=book_key, unique=True)
        if quote:
            quotes_collected.append(quote)
            preview = quote["translation"][:60]
            print(f"  [{len(quotes_collected)}/{count}] {preview}...")
        else:
            print(f"  [{i+1}/{count}] (skipped - no unique quote found)")

    if not quotes_collected:
        print("\nNo quotes could be generated.", file=sys.stderr)
        return 1

    # Write output
    with open(target, "w", encoding="utf-8") as f:
        if fmt == "json":
            f.write(json.dumps(quotes_collected, ensure_ascii=False, indent=2))
        else:
            for q in quotes_collected:
                f.write(_format_english_quote(q, with_chinese=with_chinese))
                f.write("\n\n")

    print(f"\nDone! {len(quotes_collected)}/{count} quotes saved to {target}")
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="ctext",
        description="Chinese Classics Quote CLI v3.0 - Retrieve wisdom from classical Chinese texts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py generate                          Get one short English quote
  python main.py generate --book dao-de-jing       Short quote from Dao De Jing
  python main.py generate --count 20               Generate 20 short English quotes to file
  python main.py generate --count 50 --with-chinese  Include Chinese text
  python main.py random                            Get a random quote from any book
  python main.py random --book dao-de-jing         Get a quote from Dao De Jing
  python main.py unique                            Get a quote you haven't seen before
  python main.py batch --count 10                  Generate 10 unique quotes to file
  python main.py search --query "仁"               Search for passages containing "仁"
  python main.py browse analects                   Explore the Analects structure
  python main.py download analects                 Download the Analects to a file
  python main.py list                              Show available books
  python main.py stats                             Show your quote history
  python main.py status                            Show API status
  python main.py config --show                     Show configuration
        """
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose/debug output"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- Generate command (short English quotes) ---
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate short English quotes (1-3 sentences) from classical texts"
    )
    gen_parser.add_argument(
        "--book", "-b",
        choices=list(AVAILABLE_BOOKS.keys()),
        help="Specific book to draw from (default: random)"
    )
    gen_parser.add_argument(
        "--count", "-n",
        type=int,
        default=1,
        help="Number of quotes to generate (default: 1)"
    )
    gen_parser.add_argument(
        "--output", "-o",
        help="Output file (auto-created when --count > 1)"
    )
    gen_parser.add_argument(
        "--with-chinese",
        action="store_true",
        help="Include original Chinese text below each quote"
    )
    gen_parser.add_argument(
        "--format", "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    # --- Random command ---
    random_parser = subparsers.add_parser(
        "random",
        help="Get a random quote from classical Chinese texts"
    )
    random_parser.add_argument(
        "--book", "-b",
        choices=list(AVAILABLE_BOOKS.keys()),
        help="Specific book to fetch from (use 'list' to see options)"
    )
    random_parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Skip English translation"
    )
    random_parser.add_argument(
        "--format", "-f",
        choices=["full", "minimal", "json"],
        default="full",
        help="Output format (default: full)"
    )
    
    # --- Unique command ---
    unique_parser = subparsers.add_parser(
        "unique",
        help="Get a unique quote (not seen before)"
    )
    unique_parser.add_argument(
        "--book", "-b",
        choices=list(AVAILABLE_BOOKS.keys()),
        help="Specific book to fetch from"
    )
    unique_parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Skip English translation"
    )
    unique_parser.add_argument(
        "--format", "-f",
        choices=["full", "minimal", "json"],
        default="full",
        help="Output format (default: full)"
    )
    
    # --- Batch command ---
    batch_parser = subparsers.add_parser(
        "batch",
        help="Generate multiple unique quotes to a file"
    )
    batch_parser.add_argument(
        "--count", "-n",
        type=int,
        required=True,
        help="Number of quotes to generate (required)"
    )
    batch_parser.add_argument(
        "--output", "-o",
        help="Output filename (default: quotes_<timestamp>.txt)"
    )
    batch_parser.add_argument(
        "--book", "-b",
        choices=list(AVAILABLE_BOOKS.keys()),
        help="Specific book to fetch from"
    )
    batch_parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Skip English translation"
    )
    batch_parser.add_argument(
        "--format", "-f",
        choices=["full", "json"],
        default="full",
        help="Output format (default: full)"
    )
    
    # --- List command ---
    subparsers.add_parser(
        "list",
        help="List available books"
    )
    
    # --- Stats command ---
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show quote history statistics"
    )
    stats_parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset/clear all quote history"
    )
    
    # --- Search command ---
    search_parser = subparsers.add_parser(
        "search",
        help="Search for passages containing specific text"
    )
    search_parser.add_argument(
        "--query", "-q",
        required=True,
        help="Search query (Chinese characters)"
    )
    search_parser.add_argument(
        "--book", "-b",
        choices=list(AVAILABLE_BOOKS.keys()),
        help="Limit search to specific book"
    )
    search_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Maximum results to show (default: 10)"
    )
    search_parser.add_argument(
        "--format", "-f",
        choices=["full", "json"],
        default="full",
        help="Output format (default: full)"
    )
    
    # --- Browse command ---
    browse_parser = subparsers.add_parser(
        "browse",
        help="Explore book structure and chapters"
    )
    browse_parser.add_argument(
        "book",
        choices=list(AVAILABLE_BOOKS.keys()),
        help="Book to browse"
    )
    browse_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=20,
        help="Maximum chapters to show (default: 20)"
    )
    
    # --- Download command ---
    download_parser = subparsers.add_parser(
        "download",
        help="Download full text of a book to file"
    )
    download_parser.add_argument(
        "book",
        choices=list(AVAILABLE_BOOKS.keys()),
        help="Book to download"
    )
    download_parser.add_argument(
        "--output", "-o",
        help="Output filename (default: <book>_<timestamp>.txt)"
    )
    download_parser.add_argument(
        "--format", "-f",
        choices=["paragraphs", "string"],
        default="paragraphs",
        help="Output format (default: paragraphs)"
    )
    
    # --- Status command ---
    subparsers.add_parser(
        "status",
        help="Show API status and rate limit info"
    )
    
    # --- Config command ---
    config_parser = subparsers.add_parser(
        "config",
        help="Manage configuration and API key"
    )
    config_parser.add_argument(
        "--show",
        action="store_true",
        help="Show current configuration"
    )
    config_parser.add_argument(
        "--set-apikey",
        metavar="KEY",
        help="Set API key (use 'none' to clear)"
    )
    config_parser.add_argument(
        "--set-language",
        choices=["en", "zh"],
        help="Set interface language"
    )
    config_parser.add_argument(
        "--set-remap",
        metavar="MODE",
        help="Set character remap ('gb' for simplified, 'none' for traditional)"
    )
    config_parser.add_argument(
        "--set-default-book",
        metavar="BOOK",
        help="Set default book for random quotes"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config()
    
    # Create fetcher with verbose setting
    fetcher = QuoteFetcher(config, verbose=args.verbose)
    
    # Dispatch to appropriate command
    commands = {
        "generate": lambda: cmd_generate(args, fetcher),
        "random": lambda: cmd_random(args, fetcher),
        "unique": lambda: cmd_unique(args, fetcher),
        "batch": lambda: cmd_batch(args, fetcher),
        "list": lambda: cmd_list(args, fetcher),
        "stats": lambda: cmd_stats(args, fetcher),
        "search": lambda: cmd_search(args, fetcher, config),
        "browse": lambda: cmd_browse(args, fetcher),
        "download": lambda: cmd_download(args, fetcher),
        "status": lambda: cmd_status(args, fetcher, config),
        "config": lambda: cmd_config(args, config),
    }
    
    if args.command in commands:
        try:
            sys.exit(commands[args.command]())
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(130)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
