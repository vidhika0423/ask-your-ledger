import re
from datetime import datetime
from gtts import gTTS
from num2words import num2words

def format_dollar_amount(match):
    """ $12,500 -> 'twelve thousand five hundred dollars'"""
    raw = match.group(0).replace("$","").replace(",","")
    if "." in raw:
        dollars, cents = raw.split(".")
        dollars_words = num2words(int(dollars))
        cent_words = num2words(int(cents))
        return f"{dollars_words} dollars and {cent_words} cents"
    return f"{num2words(int(raw))} dollars"

def format_invoice_id(match):
    """INV-1042 -> 'invoice I N V, one, zero, four, two'"""
    number_part = match.group(0).split("-")[1]
    digits_spoken = ", ".join(list(number_part))
    return f"I N V, {digits_spoken}"

def format_date(match):
    """2026-05-01 -> 'May 1st, 2026'"""
    date_str = match.group(0)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day = dt.day
    suffix = "th" if 11<=day % 100 <= 13 else {1:"st", 2:"nd", 3:"rd"}.get(day % 10, "th")
    return f"{dt.strftime('%B')} {day}{suffix}, {dt.year}"

def format_for_tts(text):
    text = re.sub(r"\$[\d,]+(?:\.\d+)?", format_dollar_amount, text)
    text = re.sub(r"INV-\d+", format_invoice_id,text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}", format_date,text)
    return text

def speak(text, output_path = "answer.mp3"):
    """Synthesizes the TTS-safe text into an audio file"""
    tts = gTTS(text = text, lang= "en")
    tts.save(output_path)
    print(f"Audio saved to {output_path}")

if __name__ == "__main__":
    reviewer_approved_answer = (
        "Yes, two subsidiaries of Acme Holdings are overdue: Acme Corp has "
        "invoice INV-1001 for $12,500, due 2026-05-01, and Acme Digital has "
        "invoice INV-1003 for $8,700, due 2026-06-15. Per the contract, "
        "late payments incur a 1.5% monthly penalty on the outstanding balance."
    )
 
    print("--- ORIGINAL (reviewer-approved text) ---")
    print(reviewer_approved_answer)
 
    tts_safe = format_for_tts(reviewer_approved_answer)
    print("\n--- TTS-SAFE VERSION ---")
    print(tts_safe)
 
    speak(tts_safe)
