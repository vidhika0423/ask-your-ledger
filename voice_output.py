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
    return f"invoice I N V, {digits_spoken}"

