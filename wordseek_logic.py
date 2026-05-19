import re
import math
import asyncio
import requests
import unicodedata
from telethon import TelegramClient, events

STARTING_WORD = "slate"

TARGET_URLS = [
    "https://raw.githubusercontent.com/binamralamsal/WordSeek/master/src/data/common-five.json",
    "https://raw.githubusercontent.com/binamralamsal/WordSeek/master/src/data/daily-word-lists.json"
]

RED = "🟥"
YELLOW = "🟨"
GREEN = "🟩"

print("Downloading target words...")
word_set = set()
for url in TARGET_URLS:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    for w in r.json():
        w = w.strip().lower()
        if len(w) == 5 and w.isalpha():
            word_set.add(w)

WORDS = list(word_set)
print(f"Loaded {len(WORDS)} high-probability target words!")

client = TelegramClient("wordseek_session", API_ID, API_HASH)
used_words = set()
last_text = ""

def normalize_word(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if ch.isalpha()).lower()

def parse_input(text):
    guesses = []
    for line in text.splitlines():
        colors = re.findall(r"[🟥🟨🟩]", line)
        if len(colors) != 5:
            continue
        word = normalize_word(line)
        if len(word) >= 5:
            word = word[-5:]
            guesses.append((word, colors))
    return guesses

def compute_colors(candidate, guess):
    colors = [RED] * 5
    target_counts = {}
    for c in candidate:
        target_counts[c] = target_counts.get(c, 0) + 1
    
    for i in range(5):
        if guess[i] == candidate[i]:
            colors[i] = GREEN
            target_counts[guess[i]] -= 1

    for i in range(5):
        if colors[i] != GREEN:
            g = guess[i]
            if target_counts.get(g, 0) > 0:
                colors[i] = YELLOW
                target_counts[g] -= 1
    return colors

def solve(text):
    guesses = parse_input(text)
    if not guesses:
        return []

    guessed_words = {g[0] for g in guesses}
    possible = []

    for word in WORDS:
        if word in guessed_words:
            continue
            
        ok = True
        for guess, colors in guesses:
            if compute_colors(word, guess) != colors:
                ok = False
                break
                
        if ok:
            possible.append(word)
    return possible

def get_best_word_frequency(possible_words):
    letter_counts = {}
    for word in possible_words:
        for char in set(word):
            letter_counts[char] = letter_counts.get(char, 0) + 1
            
    best_word = possible_words[0]
    best_score = -1
    for word in possible_words:
        score = sum(letter_counts[c] for c in set(word))
        if score > best_score:
            best_score = score
            best_word = word
    return best_word

def get_best_word(possible_words):
    if not possible_words:
        return None
    if len(possible_words) <= 2:
        return possible_words[0]

    if len(possible_words) > 150:
        return get_best_word_frequency(possible_words)

    best_word = possible_words[0]
    best_score = -1
    
    total = len(possible_words)
    for guess in possible_words:
        buckets = {}
        for candidate in possible_words:
            pattern = tuple(compute_colors(candidate, guess))
            buckets[pattern] = buckets.get(pattern, 0) + 1
            
        entropy = 0
        for size in buckets.values():
            p = size / total
            entropy -= p * math.log2(p)
            
        if entropy > best_score:
            best_score = entropy
            best_word = guess
            
    return best_word

@client.on(events.NewMessage(chats=TARGET_CHAT))
async def handler(event):
    global last_text

    text = event.raw_text or ""
    if text == last_text:
        return
    last_text = text
    low = text.lower()

    if "game started!" in low and "5-letter" in low:
        print("\n--- NEW GAME | INSTANT FIRST GUESS ---")
        used_words.clear()
        used_words.add(STARTING_WORD)
        await client.send_message(TARGET_CHAT, STARTING_WORD)
        return

    if "congrats! you guessed it correctly" in low or "game over! the word was" in low:
        print("\n--- GAME ENDED | INSTANT RESTART ---")
        await client.send_message(TARGET_CHAT, "/new5")
        return

    if "5-letter mode" in low and ("🟥" in text or "🟨" in text or "🟩" in text):
        answers = solve(text)
        if not answers:
            return

        valid_answers = [w for w in answers if w not in used_words]
        if not valid_answers:
            return

        best_guess = get_best_word(valid_answers)
        used_words.add(best_guess)
        
        print(f"[LIGHTNING SPEED] FIRE: {best_guess.upper()}")
        await client.send_message(TARGET_CHAT, best_guess)
        return

async def main():
    print("Starting LIGHTNING SPEED Farmer...")
    await client.start()
    print("Logged in!")
    print("Go to your group and type '/new5' to pull the trigger.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())
