# Python Version Compatibility Guide

## Issue: Python 3.13 Compatibility

The Polymarket Notifier Bot uses Playwright for advanced web scraping, but Playwright's dependency `greenlet` doesn't support Python 3.13 yet. Here are your options:

## Option 1: Use Python 3.11 or 3.12 (Recommended)

### Install Python 3.11 or 3.12

**Using Homebrew (macOS):**
```bash
# Install Python 3.11
brew install python@3.11

# Or install Python 3.12
brew install python@3.12
```

**Using pyenv (Cross-platform):**
```bash
# Install pyenv first
brew install pyenv

# Install Python 3.11
pyenv install 3.11.7

# Set as local version
pyenv local 3.11.7
```

### Create Virtual Environment
```bash
# Using Python 3.11
python3.11 -m venv polymarket_env
source polymarket_env/bin/activate

# Or using Python 3.12
python3.12 -m venv polymarket_env
source polymarket_env/bin/activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

## Option 2: Use Basic Version (No Playwright)

If you want to stick with Python 3.13, use the basic version that doesn't require Playwright:

```bash
# Install basic dependencies only
pip install requests python-dotenv tenacity beautifulsoup4

# Run the basic version
python polymarket_notifier_basic.py
```

**Note:** The basic version only scrapes the first page of leaderboards and may miss many wallets.

## Option 3: Wait for Compatibility

Monitor these issues for Python 3.13 support:
- [greenlet Python 3.13 support](https://github.com/python-greenlet/greenlet/issues/456)
- [Playwright Python 3.13 support](https://github.com/microsoft/playwright-python/issues/XXXX)

## Recommended Setup

For the best experience, use Python 3.11 or 3.12:

```bash
# 1. Install Python 3.11
brew install python@3.11

# 2. Create virtual environment
python3.11 -m venv polymarket_env
source polymarket_env/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 4. Configure environment
cp env.example .env
# Edit .env with your Telegram credentials

# 5. Run the bot
python polymarket_notifier.py
```

## Testing Installation

Run the test script to verify everything works:

```bash
python test_installation.py
```

This will test all components and show you what's working and what needs to be fixed.
